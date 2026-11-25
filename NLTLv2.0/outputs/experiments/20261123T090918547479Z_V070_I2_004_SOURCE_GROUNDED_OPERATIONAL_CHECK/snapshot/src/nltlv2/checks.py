from __future__ import annotations
import re,difflib,collections,json
from rdflib import Graph,URIRef,BNode,Literal,RDF,RDFS,XSD,Variable
from rdflib.namespace import SH
from rdflib.collection import Collection
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql import prepareQuery
from .schema import N,Q,U
from .core import finding,digest

def iri_tokens(text):
 prefixes={p:u for p,u in re.findall(r'(?i)\b(?:PREFIX|@prefix)\s+([\w-]+):\s*<([^>]+)>',text)}
 tokens=set(re.findall(r'<([A-Za-z][A-Za-z0-9+.-]*:[^<>\s]*)>',text))
 tokens|={prefixes[p]+local for p,local in re.findall(r'(?<![\w:/])([\w-]+):([A-Za-z_][\w.-]*)',text) if p in prefixes}
 return tokens-set(prefixes.values())
def sparql_checks(c,query,evidence='Parsed SPARQL/SHACL analysis',*,scope='SHACL-SPARQL',slot='query'):
 from .sparql_analysis import analyze
 out=analyze(c,query,scope=scope,slot=slot)[0]
 try:
  from .sparql_analysis import children
  from rdflib.plugins.sparql.parserutils import CompValue
  stack=[parseQuery(query)]
  while stack:
   node=stack.pop()
   if isinstance(node,CompValue) and node.name in ['ServiceGraphPattern','DatasetClause']:
    out.append(finding(c,'SPARQL_ERROR','External dataset/service access is outside local execution policy',query,expected='Local data and supplied ontology only',evidence='Production execution policy, not a regulatory conformance judgment',suggestion='Use supplied local data; record missing external evidence as unresolved instead of executing a remote query.',location='SPARQL '+node.name,contract_id=scope,check_id='external-data-policy'))
   stack.extend(v for _,v in children(node))
 except Exception:pass
 return out

def check(c,schema,rid):
 out=[]
 for issue in schema.context_issues.get(rid,[]):out.append(finding(c,'UNRESOLVED_CONTEXT','Source context requires reconciliation',issue['excerpt'],expected=issue['disposition'],evidence=json.dumps(issue),suggestion='Resolve the source/contract exception before judging or repairing code.',location='source '+issue['source_clause'],confirmed=False))
 try:g=Graph().parse(data=c.code,format='turtle')
 except Exception as e:
  match=re.search(r'at line (\d+)',str(e));line=int(match.group(1)) if match else None
  excerpt=c.code.splitlines()[line-1] if line and line<=len(c.code.splitlines()) else c.code
  return [finding(c,'PARSE_ERROR','Turtle parse failed',excerpt,evidence='rdflib Turtle parser',suggestion='Correct only the reported syntax.',location='Turtle parser'+(' line '+str(line) if line else ''),diagnostic=str(e))]
 from .activation import checks as activation_checks
 out+=activation_checks(c,g)
 ids={str(x) for triple in g for x in triple if isinstance(x,URIRef)}
 query_iris=set()
 for q in g.objects(None,SH.select):query_iris|=iri_tokens(str(q))
 ids|=query_iris
 # A declared SHACL shape identifier is an artifact name, not a regulatory operand.
 defined_shapes=set(g.subjects(RDF.type,SH.NodeShape))|set(g.subjects(RDF.type,SH.PropertyShape))
 regulatory_uses={p for _,p,_ in g}|query_iris
 for predicate in [SH.path,SH['class'],SH.targetClass,SH.datatype,SH.hasValue,RDF.first]:regulatory_uses.update(g.objects(None,predicate))
 ids-={str(x) for x in defined_shapes-regulatory_uses if isinstance(x,URIRef)}
 for i in sorted(ids):
  if i.startswith(str(N)) and i not in schema.canonical or i.startswith(str(U)) and i not in schema.units or i.startswith(str(Q)) and i not in {str(Q.unit),str(Q.numericValue),str(Q.QuantityValue)}:
   replacement,evidence=schema.identifier_correction(i)
   out.append(finding(c,'CANONICAL_IDENTIFIER_ERROR','Identifier absent from locked canonical metadata',i,expected=replacement or 'An evidenced canonical identifier; no inferred replacement',evidence=json.dumps(evidence),suggestion=('Replace '+i+' with '+replacement+' at the reported path/query. Repair the constraint; do not delete numeric, datatype, unit or query obligations. Preserve values and unrelated constraints. This identifier correction performs no conversion.') if replacement else 'Resolve against source metadata; do not guess or remove an obligation to silence this diagnostic.',location='IRI '+i,contract_id='schema-identifiers',obligation_id=i,check_id='canonical-identifier',diagnostic='Identifier absent from locked canonical metadata: '+i))
 def pathitems(node):
  if isinstance(node,URIRef):return [str(node)]
  try:return [str(x) for x in Collection(g,node)] if (node,RDF.first,None) in g else None
  except Exception:return None
 # Canonical constraint predicates/classes are checked regardless of namespace;
 # artifact shape names and ordinary data-instance IRIs are not mistaken for terms.
 for position in [SH.path,SH['class'],SH.targetClass]:
  for value in g.objects(None,position):
   values=[value] if isinstance(value,URIRef) else [x for x in (pathitems(value) or [])]
   for value in values:
    iri=str(value)
    if iri not in schema.canonical and iri!=str(RDF.type):
     if any(f.category=='CANONICAL_IDENTIFIER_ERROR' and f.excerpt==iri for f in out):continue
     replacement,evidence=schema.identifier_correction(iri)
     out.append(finding(c,'CANONICAL_IDENTIFIER_ERROR','Constraint uses an undeclared schema identifier',iri,expected=replacement or 'An explicitly declared schema term; mapping unresolved',evidence=json.dumps(evidence),suggestion=('Replace only the identifier with '+replacement+'; repair rather than delete this constraint. Preserve numeric values, units and other obligations.') if replacement else 'Resolve the schema mapping without inventing a term or silently deleting obligations.',location=str(position),contract_id='schema-identifiers',obligation_id=iri,check_id='canonical-identifier'))
 root,allowed=schema.allowed_paths(rid)
 owner_contract=schema.effective_owners(rid)
 def property_checks(ps,path):
  # Direct datatype restrictions must admit the locked canonical numeric encoding.
  # This does not declare other numeric RDF literals illegal globally.
  if path and path[-1]==str(Q.numericValue):
   datatype=g.value(ps,SH.datatype);expected=schema.quantity_profile['canonical_literal_encoding']
   if datatype is not None and str(datatype)!=expected:
    out.append(finding(c,'TERM_KIND_ERROR','Numeric operand datatype restriction rejects the locked canonical decimal encoding',str(datatype),expected=expected,evidence=json.dumps(schema.quantity_profile),suggestion='Accept the canonical decimal encoding (or an evidenced compatible numeric validation), without coercing values or relabelling units.',location='sh:datatype on qudt:numericValue'))
  for idx,prop in enumerate(path or []):
   term=schema.terms.get(prop,{})
   if not term:continue
   kind=term.get('kind');dt=g.value(ps,SH.datatype)
   if idx==len(path)-1:
    if dt is not None:
     if kind in ['ObjectProperty','QuantityProperty']:
      out.append(finding(c,'TERM_KIND_ERROR','Object-valued property constrained as a literal',str(dt),expected='sh:class / sh:node for '+prop,evidence=json.dumps(term),suggestion='Constrain the object/quantity node; constrain qudt:numericValue as decimal separately.',location='sh:datatype on '+prop))
     elif term.get('datatype'):
      expected=term['datatype'].replace('xsd:',str(XSD))
      if str(dt)!=expected:out.append(finding(c,'TERM_KIND_ERROR','Datatype conflicts with locked property datatype',str(dt),expected=expected,evidence=json.dumps(term),suggestion='Use the explicit property datatype; do not reinterpret literal values.',location='sh:datatype on '+prop))
    for val in g.objects(ps,SH.hasValue):
     if kind in ['ObjectProperty','QuantityProperty'] and isinstance(val,Literal):out.append(finding(c,'TERM_KIND_ERROR','Object-valued property compared to literal',val.n3(),expected='Canonical object IRI or quantity node',evidence=json.dumps(term),suggestion='Use the evidenced object representation.',location='sh:hasValue on '+prop))
     if kind=='DatatypeProperty' and isinstance(val,URIRef):out.append(finding(c,'TERM_KIND_ERROR','Literal-valued property compared to IRI',str(val),expected=term.get('datatype','literal'),evidence=json.dumps(term),suggestion='Use the evidenced literal datatype.',location='sh:hasValue on '+prop))
    if kind=='QuantityProperty':
     nested=[ps]+list(g.objects(ps,SH.node))
     for n in nested:
      for child in g.objects(n,SH.property):
       if g.value(child,SH.path)==Q.unit:
        for unit in g.objects(child,SH.hasValue):
         if str(unit)!=term.get('unitIri'):out.append(finding(c,'UNIT_CONSISTENCY_ERROR','Property unit differs from canonical scale/representation',str(unit),expected=term.get('unitIri','unresolved'),evidence=json.dumps(term),suggestion='Establish numeric conversion and required representation from source; renaming a unit is insufficient.',location='quantity unit on '+prop))
  if path:
   for i,prop in enumerate(path):
    if prop in allowed and allowed[prop] and tuple(path[:i+1]) not in allowed[prop]:
     out.append(finding(c,'PATH_CONTRACT_ERROR','Complete property path conflicts with explicit ownership contract',' / '.join(path),expected=json.dumps(allowed[prop]),evidence=json.dumps(dict(termOwners=owner_contract,modelPaths=schema.bindings.get(rid,{}).get('model_paths',[]))),suggestion='Follow the evidenced complete path; preserve the remaining obligation.',location='sh:path '+prop))
    elif prop.startswith(str(N)) and 'Property' in schema.terms.get(prop,{}).get('kind','') and prop not in allowed:
     out.append(finding(c,'UNRESOLVED_CONTEXT','No explicit ownership/path contract for used property',prop,expected='Source-backed owner binding before path judgment',evidence='No termOwners entry; RDFS domain is not exclusive ownership',suggestion='Document and resolve representation evidence; do not assume ship.',location='owner '+prop,confirmed=False,blocking=False,assessment='UNSPECIFIED_REPRESENTATION'))
 def visit(node,prefix,stack):
  if node in stack:return
  stack=stack|{node}
  for ps in g.objects(node,SH.property):
   local=pathitems(g.value(ps,SH.path));path=prefix+local if local else None
   property_checks(ps,path)
   if path:visit(ps,path,stack)
  for child in g.objects(node,SH.node):visit(child,prefix,stack)
  for op in [SH['or'],SH['and'],SH.xone]:
   for head in g.objects(node,op):
    for child in Collection(g,head):visit(child,prefix,stack)
  for child in g.objects(node,SH['not']):visit(child,prefix,stack)
 targets=list(g.subject_objects(SH.targetClass))
 for shape,cls in targets:
  if root and schema.subtype(cls,N[root]):visit(shape,[],set())
  elif root:
   # A contract-owned subclass target can represent an inner owner directly.
   owners=set(owner_contract.values());matching=[o for o in owners if schema.subtype(cls,N[o])]
   routes=[]
   for prop,paths in allowed.items():
    if str(owner_contract.get(prop.removeprefix(str(N)),'')) in matching:routes += [list(p[:-1]) for p in paths]
   if matching and routes:visit(shape,min(routes,key=len),set())
   else:out.append(finding(c,'UNRESOLVED_CONTEXT','Target cannot be bound to an explicit model owner',str(cls),expected=root,evidence='termOwners/modelPaths and rdfs:subClassOf closure',suggestion='Resolve target applicability from source and contract.',location='sh:targetClass',confirmed=False,blocking=False,assessment='UNSPECIFIED_REPRESENTATION'))
  else:visit(shape,[],set())
 for dtype in g.objects(None,SH.datatype):
  valid={'string','boolean','decimal','integer','int','long','short','byte','nonNegativeInteger','positiveInteger','nonPositiveInteger','negativeInteger','unsignedLong','unsignedInt','unsignedShort','unsignedByte','double','float','date','dateTime','time','duration','dayTimeDuration','yearMonthDuration','anyURI','normalizedString','token','language','Name','NCName','NMTOKEN','hexBinary','base64Binary','gYear','gMonth','gDay','gYearMonth','gMonthDay'}
  if not isinstance(dtype,URIRef) or str(dtype).startswith(str(XSD)) and str(dtype).removeprefix(str(XSD)) not in valid:
   out.append(finding(c,'TERM_KIND_ERROR','Unsupported or invalid datatype IRI',str(dtype),expected='Valid declared XML Schema/RDF datatype',evidence='XML Schema datatype vocabulary and locked metadata',suggestion='Use the declared property datatype.',location='sh:datatype'))
 for qi,q in enumerate([v for predicate in [SH.select,SH.ask,SH.construct] for v in g.objects(None,predicate)]):
  text=str(q);out+=sparql_checks(c,text,scope="SHACL-SPARQL:"+rid,slot="select["+str(qi)+"]")
  # Supported simple BGP path tracking. Complex branches are explicitly outside owner inference.
  prefixes={p:u for p,u in re.findall(r'(?i)\bPREFIX\s+(\w+):\s*<([^>]+)>',text)}
  def iri(x):return x[1:-1] if x.startswith('<') else prefixes.get(x.split(':')[0],'')+x.split(':',1)[-1]
  for subj,pred,quote,lex in re.findall(r'([?$]\w+)\s+(<[^>]+>|[\w-]+:[\w.-]+)\s+([\"\'])([^\"\']*)[\"\']',text):
   term=schema.terms.get(iri(pred),{})
   if term.get('kind') in ['ObjectProperty','QuantityProperty']:
    out.append(finding(c,'TERM_KIND_ERROR','SPARQL object-valued predicate compared to literal',pred+' '+quote+lex+quote,expected='Canonical object IRI / QuantityValue',evidence=json.dumps(term),suggestion='Use the explicit object representation; do not compare a quantity node to its numeric value.',location='sh:select object'))
  if not re.search(r'\b(OPTIONAL|UNION|SERVICE|MINUS|EXISTS)\b',text,re.I):
   edges=re.findall(r'([?$]\w+)\s+(<[^>]+>|[\w-]+:[\w.-]+)\s+([?$]\w+|<[^>]+>|[\w-]+:[\w.-]+)',text)
   routes={'this':[]}
   for _ in range(len(edges)+1):
    for s,p,o in edges:
     s=s[1:];pred=iri(p)
     if s in routes:
      route=routes[s]+[pred]
      if o.startswith(('?','$')) and o[1:] not in routes:routes[o[1:]]=route
      if pred in allowed and allowed[pred] and tuple(route) not in allowed[pred]:
       out.append(finding(c,'PATH_CONTRACT_ERROR','SPARQL path conflicts with explicit contract',' / '.join(route),expected=json.dumps(allowed[pred]),evidence=json.dumps(owner_contract),suggestion='Bind the operand along the complete explicit model path.',location='sh:select path '+pred))
      term=schema.terms.get(pred,{})
      if term.get('unitIri') and o.startswith(('?','$')):
       for qs,qp,qo in edges:
        if qs[1:]==o[1:] and iri(qp)==str(Q.unit) and not qo.startswith(('?','$')) and iri(qo)!=term['unitIri']:
         out.append(finding(c,'UNIT_CONSISTENCY_ERROR','SPARQL operand unit incompatible with property scale',qo,expected=term['unitIri'],evidence=json.dumps(term),suggestion='Use source-supported conversion; do not relabel a numeric value.',location='sh:select unit '+pred))
 if any(g.objects(None,SH.js)) or any(g.objects(None,SH.construct)) or any(g.objects(None,SH.rule)):
  out.append(finding(c,'UNRESOLVED_CONTEXT','Rule/JavaScript execution is outside supported validation scope','',expected='Supported local SHACL constraints or an explicit execution-scope decision',evidence='Checker coverage policy; no regulatory answer inferred',suggestion='Represent the constraint using supported validation constructs or resolve execution scope; do not silently ignore executable rules.',location='unsupported SHACL execution form',confirmed=False,assessment='UNSUPPORTED_EXECUTION_FORM'))
 # Exact RDF-term matching is sometimes intentional. Flag numeric identity for
 # source review without supplying a per-regulation value or calling it a defect.
 for ps,value in g.subject_objects(SH.hasValue):
  if isinstance(value,Literal) and value.datatype in {XSD.decimal,XSD.integer,XSD.double,XSD.float}:
   out.append(finding(c,'NUMERIC_TERM_REVIEW','Numeric RDF-term identity needs source interpretation',value.n3(),expected='Decide from source whether value equality or exact RDF identity is required',evidence='SHACL sh:hasValue uses RDF-term matching; numeric spellings can denote equal values',suggestion='Inspect source and this constraint. If source requires numeric equality, use a numeric comparison while retaining required datatype and units; otherwise retain exact-term matching.',location='sh:hasValue numeric literal',confirmed=False,assessment='STATIC_WARNING',blocking=False))
 return list({f.key:f for f in out}.values())

def runtime_probe(c,schema):
 """Approved schema-derived synthetic empty targets; conformance is deliberately ignored."""
 from pyshacl import validate
 from .sparql_extensions import register_math_functions
 register_math_functions();g=Graph().parse(data=c.code,format='turtle');witness=Graph()
 from .activation import analyze
 activation=analyze(g)
 for i,cls in enumerate(g.objects(None,SH.targetClass)):witness.add((URIRef('urn:nltlv2:approved-empty-target:'+str(i)),RDF.type,cls))
 for i,p in enumerate(g.objects(None,SH.targetSubjectsOf)):witness.add((URIRef('urn:nltlv2:approved-subject:'+str(i)),p,URIRef('urn:nltlv2:probe-object')))
 for i,p in enumerate(g.objects(None,SH.targetObjectsOf)):witness.add((URIRef('urn:nltlv2:probe-subject'),p,URIRef('urn:nltlv2:approved-object:'+str(i))))
 for n in g.subjects(RDF.type,SH.NodeShape):
  if (n,RDF.type,RDFS.Class) in g:witness.add((URIRef('urn:nltlv2:approved-implicit-target'),RDF.type,n))
 try:
  _,report,_=validate(witness,shacl_graph=g,ont_graph=schema.graph,inference='rdfs',advanced=True,abort_on_first=False,meta_shacl=False)
  if not isinstance(report,Graph):raise RuntimeError(str(report))
  return [],dict(policy='Schema-derived synthetic empty targets only; never evaluation fixtures',ignored_conformance=True,activation=activation,witness=witness.serialize(format='turtle'))
 except Exception as e:
  from .execution_policy import classify,diagnostic
  kind=classify(e);candidate=kind=='CANDIDATE_ERROR'
  return [finding(c,'SPARQL_ERROR' if candidate else 'RESOURCE_UNCERTAIN' if kind=='RESOURCE_UNCERTAIN' else 'INFRASTRUCTURE_ERROR','Local SHACL execution failed; not a conformance verdict',c.code,expected='Executable SHACL on approved synthetic development input',evidence='Schema-derived empty-target runtime probe',suggestion='Correct the attributable generated-query diagnostic without changing source obligations.' if candidate else 'Stop dispatch; investigate runtime/resources without blaming or automatically repairing code.',location='local runtime',diagnostic=diagnostic(e),confirmed=candidate,assessment='CONFIRMED_CANDIDATE_QUERY_ERROR' if candidate else kind,contract_id='SHACL-runtime',obligation_id='execution',check_id='engine.execution')],dict(error=diagnostic(e),failure_kind=kind,not_conformance=True)
