import sys,json,re,collections,hashlib,csv
from pathlib import Path
from rdflib import Graph,URIRef,Literal,Namespace,RDF,XSD
from rdflib.collection import Collection
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue
ROOT=Path.cwd();D=Path(__file__).resolve().parent;A=json.loads((ROOT/'evaluation_audit/authoritative_run.json').read_text());BASE=Path(A['run_dir']);RECS=json.loads(Path(A['current_case_records']).read_text());ROWS=json.loads((BASE/'retained_rows.json').read_text());S=Namespace('http://www.w3.org/ns/shacl#');Q=Namespace('http://qudt.org/schema/qudt/');N=Namespace('https://w3id.org/nltl/vocab#');U='http://qudt.org/vocab/unit/'
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(D/n).write_text(json.dumps(x,indent=2,default=str)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def nodes(x):
 if isinstance(x,URIRef):yield x
 elif isinstance(x,dict):
  for v in x.values():yield from nodes(v)
 elif isinstance(x,(list,tuple,set)):
  for v in x:yield from nodes(v)
def used_nodes(g):
 out=set(x for x in g.all_nodes() if isinstance(x,URIRef));errors=[]
 for q in g.objects(None,S.select):
  try:out.update(nodes(prepareQuery(str(q)).algebra))
  except Exception as e:errors.append(str(e))
 return out,errors
def qty_consts(g,prop):
 seen=set();pending=list(g.objects(prop,S.node))+[prop];out=[]
 while pending:
  n=pending.pop()
  if n in seen:continue
  seen.add(n)
  path=g.value(n,S.path)
  if path==Q.unit:
   out.extend((n,o) for o in g.objects(n,S.hasValue))
   for h in g.objects(n,S['in']):out.extend((n,o) for o in Collection(g,h))
  if path is not None and str(path).startswith(str(N)) and n!=prop:continue
  for p in [S.property,S.node]:pending.extend(g.objects(n,p))
  for p in [S['or'],S['and'],S.xone]:
   for h in g.objects(n,p):pending.extend(Collection(g,h))
 return out
snapshot={};findings=[];traces=[];shapes=[]
units=set()
for row in ROWS:
 k=row['condition'],row['requirement_id']
 if k in snapshot:continue
 snapshot[k]=row
 for t in read(row['requirement_context_path'])['terms']:
  if t.get('recommendedUnit'):units.add(t['recommendedUnit'])
for (w,req),row in snapshot.items():
 manifest_context=ROOT/row['generation_manifest_record']['context_pack_path'].removeprefix('MVP/')
 run=manifest_context.parents[1]
 diag=run/'artifacts/attempt_01'/('no_semantic_validator_diagnostics.json' if w=='NO_SEMANTIC' else 'singleshot_diagnostics.json')
 if not diag.exists():
  ds=list((run/'artifacts/attempt_01').glob('*diagnostics*json'));diag=ds[0] if ds else None
 calls=run/'tables/api_calls.csv';iterations=run/'tables/iterations.csv'
 roles=collections.Counter()
 if calls.exists():
  for c in csv.DictReader(calls.open()):
   if c.get('STATUS')=='COMPLETED':roles[c.get('ROLE')]+=1
 dp=read(diag) if diag else {};dv=dp.get('deterministicValidation',dp.get('deterministic_validation',{}))
 traces.append(dict(condition=w,requirement_id=req,original_eligible=row['original_eligible'],run=str(run),diagnostics=str(diag),diagnostics_sha256=sha(diag) if diag else None,roles=dict(roles),deterministic=dv,call_table=str(calls),iterations=str(iterations),saved_diagnostics=dp))
 if not row['original_eligible'] or not Path(row['shape_path']).is_file():continue
 g=Graph().parse(row['shape_path']);terms={t['iri']:t for t in read(row['requirement_context_path'])['terms']};uris,errors=used_nodes(g)
 common=[c for c,r in RECS.items() if r['requirement_id']==req and r['state'] in ['COMPLETED','COMPLETED_PRIOR50']]
 exposure=[r['case_id'] for r in ROWS if r['requirement_id']==req and r['condition']==w]
 shape=dict(condition=w,requirement_id=req,path=row['shape_path'],sha256=sha(row['shape_path']),reviewed_cases=common,retained_exposure=exposure,query_analysis_errors=errors,context=row['requirement_context_path'],source_clause=row['source_clause'],source_text=row['frozen_requirement_text'])
 shapes.append(shape)
 for uri in sorted(uris,key=str):
  if str(uri).startswith(str(Q)) and U+str(uri).split('/')[-1] in units:
   findings.append(dict(**shape,family='WRONG_IRI_NAMESPACE',mechanism='QUDT_SCHEMA_NAMESPACE_USED_AS_UNIT',bad=str(uri),expected=U+str(uri).split('/')[-1],certainty='CONFIRMED_STATIC',secondary='UNIT_LITERAL',effect='Valid canonical quantities fail matching; joins may also suppress intended rejection.',excerpt=[line.strip() for line in Path(row['shape_path']).read_text().splitlines() if str(uri) in line or 'qudt:'+str(uri).split('/')[-1] in line]))
 for n,path in g.subject_objects(S.path):
  meta=terms.get(str(path),{});expected=meta.get('recommendedUnit')
  if meta.get('kind')=='QuantityProperty' and expected:
   for qn,value in qty_consts(g,n):
    if str(value)!=expected:
     findings.append(dict(**shape,family='UNIT_LITERAL',mechanism='QUANTITY_CANONICAL_UNIT_MISMATCH',property=str(path),bad=str(value),expected=expected,certainty='CONFIRMED_STATIC',secondary='WRONG_IRI_NAMESPACE' if str(value).startswith(str(Q)) else None,effect='Canonical valid quantity rejected; formula may compare differently scaled operands.',excerpt=f'sh:path <{path}>; quantity node -> sh:path qudt:unit; sh:hasValue <{value}>',metadata=meta))
  if meta.get('datatype')=='xsd:string':
   vals=list(g.objects(n,S.hasValue))
   for h in g.objects(n,S['in']):vals+=list(Collection(g,h))
   plain=[v.n3() for v in vals if isinstance(v,Literal) and v.datatype is None and not v.language]
   if plain:findings.append(dict(**shape,family='UNIT_LITERAL',mechanism='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY',property=str(path),bad=plain,expected='xsd:string identity in the recorded engine',certainty='CONFIRMED_RUNTIME_COMPATIBILITY_NOT_REGULATORY_LOGIC',effect='Typed canonical strings fail Core exact-term comparisons; not a natural-language value mismatch.',excerpt=f'sh:path <{path}>; sh:hasValue/sh:in {plain}',metadata=meta))
save('authority_snapshot.json',A);save('static_findings.json',findings);save('shape_inventory.json',shapes);save('execution_trace_audit.json',traces);save('protected_inputs.json',{str(p):sha(p) for p in [ROOT/'evaluation_audit/authoritative_run.json',Path(A['current_case_records']),Path(A['current_ordinary_results']),BASE/'retained_rows.json']})
print('eligible shapes',len(shapes),'traces',len(traces))
for mech in sorted({f['mechanism'] for f in findings}):
 print(mech)
 for w in ['NO_SEMANTIC','SINGLESHOT']:
  fs=[f for f in findings if f['condition']==w and f['mechanism']==mech];req={f['requirement_id'] for f in fs};cs={c for f in fs for c in f['reviewed_cases']};print(w,len(req),'shapes/requirements',len(cs),'reviewed exposure',sorted(req))
for w in ['NO_SEMANTIC','SINGLESHOT']:
 ts=[t for t in traces if t['condition']==w];print('trace roles',w,sum(t['roles'].get('generator',0) for t in ts),sum(t['roles'].get('syntax_repair',0) for t in ts),sum(t['roles'].get('validator',0) for t in ts))
