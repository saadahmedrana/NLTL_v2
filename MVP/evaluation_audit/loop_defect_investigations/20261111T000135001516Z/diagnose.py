import sys,json,re,hashlib,copy,time,argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from rdflib import Graph,URIRef,Literal,BNode,RDF,XSD
from rdflib.collection import Collection
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'evaluation_audit'));import audit
D=Path(__file__).resolve().parent;A=audit.read(ROOT/'evaluation_audit/authoritative_run.json');BASE=Path(A['run_dir']);RECS=audit.read(A['current_case_records']);ROWS=audit.read(BASE/'retained_rows.json');ROW={(r['condition'],r['case_id']):r for r in ROWS};S,Q,N=audit.S,audit.Q,audit.N
STATIC=audit.read(D/'static_findings.json');ORD={(r['condition'],r['case_id']):r for r in audit.read(A['current_ordinary_results'])}
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,default=str)+'\n')
def save(p,x):write(D/p,x)
def export(g,p):p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(audit.triples(g))+'\n');return str(p)
def transform(row,arm):
 g=Graph().parse(row['shape_path']);h=audit.clone(g);changes=[];req=row['requirement_id'];w=row['condition']
 if arm=='canonical_operands':
  fs=[f for f in STATIC if f['condition']==w and f['requirement_id']==req]
  for f in fs:
   if f['mechanism']=='QUDT_SCHEMA_NAMESPACE_USED_AS_UNIT':
    old,new=URIRef(f['bad']),URIRef(f['expected'])
    for s,p,o in list(h):
     if o==old:h.remove((s,p,o));h.add((s,p,new));changes.append(dict(kind='UNIT_IRI',old=str(old),new=str(new)))
     elif p==S.select:
      q=str(o);local=f['bad'].split('/')[-1]
      # Only the exact resolved qudt prefix / full IRI identified by the scan.
      q2=re.sub(r'\bqudt:'+re.escape(local)+r'\b','<'+str(new)+'>',q).replace('<'+str(old)+'>','<'+str(new)+'>')
      if q2!=q:h.set((s,p,Literal(q2)));changes.append(dict(kind='QUERY_UNIT_IRI',old=str(old),new=str(new)))
   if f['mechanism']=='RDFLIB_PLAIN_VS_XSD_STRING_COMPATIBILITY':
    for n in h.subjects(S.path,URIRef(f['property'])):
     for o in list(h.objects(n,S.hasValue)):
      if isinstance(o,Literal) and o.datatype is None and not o.language:h.set((n,S.hasValue,Literal(str(o),datatype=XSD.string)));changes.append(dict(kind='EXACT_TERM_STRING_COMPATIBILITY',property=f['property'],value=str(o)))
     for head in h.objects(n,S['in']):
      cursor=head
      while cursor!=RDF.nil:
       o=h.value(cursor,RDF.first)
       if isinstance(o,Literal) and o.datatype is None and not o.language:h.set((cursor,RDF.first,Literal(str(o),datatype=XSD.string)));changes.append(dict(kind='EXACT_TERM_STRING_COMPATIBILITY',property=f['property'],value=str(o)))
       cursor=h.value(cursor,RDF.rest)
 elif arm in ['scope_only','scope_and_additional_power'] and w=='NO_SEMANTIC':
  assert req=='TRF-017'
  for s,q in list(h.subject_objects(S.select)):
   query=str(q);common='''$this nltl:propulsionOutputRestrictionApplies ?restriction ; nltl:maximumContinuousRatingPower ?maximumPower .
?maximumPower qudt:numericValue ?maximumValue ; qudt:unit unit:KiloW .'''
   q2=query.replace('FILTER (?restriction = true)',common+'\nFILTER (?restriction = true)').replace('FILTER (?restriction = false)',common+'\nFILTER (?restriction = false)')
   if arm=='scope_and_additional_power':
    extra='''OPTIONAL { $this nltl:additionalPropulsionPower ?additionalPower . ?additionalPower qudt:numericValue ?additionalValue ; qudt:unit unit:KiloW . }
BIND((?comparisonValue + COALESCE(?additionalValue,0)) AS ?expectedComparison)
FILTER (?maximumValue != ?expectedComparison)'''
    q2=q2.replace('FILTER (?maximumValue != ?comparisonValue)',extra)
   assert q2!=query;h.set((s,S.select,Literal(q2)));changes.append(dict(kind=arm,old=query,new=q2))
 elif arm=='violation_polarity' and w=='SINGLESHOT':
  assert req=='I2-004'
  for s,q in list(h.subject_objects(S.select)):
   query=str(q);start=query.index('                $this nltl:hasUpperIceWaterlineCase ?case .');body=query[start:query.rfind('            }')]
   q2=query[:start]+'FILTER NOT EXISTS {\n'+body+'\n}\n            }\n';h.set((s,S.select,Literal(q2)));changes.append(dict(kind=arm,old=query,new=q2))
 elif arm=='paired_boolean_branch' and w=='NO_SEMANTIC':
  assert req=='IMO26-014'
  target=next(h.subjects(S.targetClass,N.ship));head=h.value(target,S['or']);branches=list(Collection(h,head));assert len(branches)==3
  # Reuse the original clauses, but pair false selector AND count>=2.
  false_branch=BNode();h.add((false_branch,S.property,branches[1]));h.add((false_branch,S.property,branches[2]));newhead=BNode();Collection(h,newhead,[branches[0],false_branch]);h.set((target,S['or'],newhead));changes.append(dict(kind=arm,source='Source exception: daylight=true OR (daylight=false AND illumination>=2). No selector/cardinality beyond the reviewed contract.'))
 elif arm=='explicit_owner_path' and w=='SINGLESHOT':
  assert req=='TRF-036'
  for n in list(h.subjects(S.path,N.iceClass)):
   inverse=BNode();head=BNode();h.add((inverse,S.inversePath,N.hasIceClassDesignParameterSet));Collection(h,head,[inverse,N.iceClass]);h.set((n,S.path,head));changes.append(dict(kind=arm,old='parameterSet/iceClass',new='parameterSet/^hasIceClassDesignParameterSet/iceClass',evidence='Locked termOwners/TRF-036/iceClass=ship; parameter set is reached from ship by hasIceClassDesignParameterSet.'))
 return g,h,changes

def setup():
 arms={'canonical_operands':['TRF-018','TRF-080','IMO-031','TRF-076'],'scope_only':['TRF-017'],'scope_and_additional_power':['TRF-017'],'violation_polarity':['I2-004'],'paired_boolean_branch':['IMO26-014'],'explicit_owner_path':['TRF-036']};jobs=[];transforms=[];plan=[]
 for arm,reqs in arms.items():
  for req in reqs:
   for w in audit.WORKFLOWS:
    rr=[r for r in ROWS if r['condition']==w and r['requirement_id']==req];row=rr[0]
    if not row['original_eligible']:
     plan.append(dict(arm=arm,requirement_id=req,condition=w,status='NO_VERDICT'));continue
    g,h,changes=transform(row,arm);changed=set(g)!=set(h);shape=export(h,D/'shapes'/arm/w/(req+'.ttl')) if changed else row['shape_path']
    transforms.append(dict(arm=arm,requirement_id=req,condition=w,changed=changed,original_shape=row['shape_path'],original_sha256=audit.sha(row['shape_path']),diagnostic_shape=shape,diagnostic_sha256=audit.sha(shape),changes=changes))
    for rr0 in rr:
     cid=rr0['case_id'];entry=dict(arm=arm,requirement_id=req,condition=w,case_id=cid,expected=rr0['expected'],shape=shape,shape_changed=changed,negative_or_positive=str(Path(A['current_fixture_revision'])/rr0['rdf_path']),baseline=ORD[w,cid]['corrected_conforms'],baseline_report=ORD[w,cid]['corrected_report'])
     if cid in RECS and RECS[cid]['state'] in ['COMPLETED','COMPLETED_PRIOR50']:
      r=RECS[cid];v=r['workflows'][w];entry['prior_strict_status']=v['status'];rp=r.get('repaired_fixture') or v.get('repaired_fixture')
      if not rp:
       spec=next(s for s in audit.read(r['specification']) if s['case']==cid);bad=Graph().parse(entry['negative_or_positive']);good=audit.clone(bad)
       for t in audit.load_triples(spec['removed_triples']):assert t in good;good.remove(t)
       for t in audit.load_triples(spec['added_triples']):good.add(t)
       rp=export(good,D/'pairs'/cid/'repaired_fixture.ttl')
      entry['repaired_fixture']=rp;entry['baseline_pair']=v
     plan.append(entry)
     if changed:
      jobs.append(dict(key=f'{arm}/{w}/{cid}/negative_or_positive',data=entry['negative_or_positive'],shape=shape))
      if entry.get('repaired_fixture'):jobs.append(dict(key=f'{arm}/{w}/{cid}/repaired',data=entry['repaired_fixture'],shape=shape))
 save('diagnostic_plan.json',plan);save('diagnostic_transformations.json',transforms);save('diagnostic_jobs.json',jobs);print('jobs',len(jobs),'changed shapes',sum(t['changed'] for t in transforms),flush=True)

def execute(j):
 folder=D/'diagnostics'/j['key'];folder.mkdir(parents=True,exist_ok=True);cache=folder/'execution.json';fp=dict(data=audit.sha(j['data']),shape=audit.sha(j['shape']),options=audit.OPTIONS)
 if cache.exists() and audit.read(cache)['fingerprint']==fp:return dict(j,result=audit.read(cache)['result'],reused=True)
 start=time.monotonic();out=audit.validate(Graph().parse(j['data']),Graph().parse(j['shape']),folder,'diagnostic');write(cache,dict(fingerprint=fp,result=out));return dict(j,result=out,seconds=time.monotonic()-start,reused=False)
def run():
 jobs=audit.read(D/'diagnostic_jobs.json');results=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  futs=[pool.submit(execute,j) for j in jobs]
  for i,f in enumerate(as_completed(futs),1):
   r=f.result();results.append(r);save('execution_progress.json',results)
   if i%20==0:print('checkpoint',i,len(jobs),flush=True)
 save('diagnostic_executions.json',results)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['setup','run']);a=p.parse_args();setup() if a.phase=='setup' else run()
