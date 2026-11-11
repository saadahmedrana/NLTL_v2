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
def sparql_checks(c,query,evidence='SPARQL 1.1 parse and simple SELECT/BGP binding analysis'):
 out=[]
 try:parseQuery(query);algebra=prepareQuery(query).algebra
 except Exception as e:return [finding(c,'SPARQL_ERROR','Embedded query does not parse',query,evidence=evidence,suggestion='Correct the exact SPARQL parser diagnostic.',location='sh:select',diagnostic=f'{type(e).__name__}: {e}')]
 projected={str(x) for x in algebra.get('PV',[]) if isinstance(x,Variable)}
 if 'this' not in projected:out.append(finding(c,'SPARQL_ERROR','SHACL SELECT must project ?this',query,expected='SELECT $this ...',evidence='SHACL-SPARQL constraint SELECT result contract',suggestion='Project $this without changing filtering logic.',location='sh:select'))
 # Conservative guaranteed binding for flat BGP + BIND. OPTIONAL/UNION/subqueries are not claimed covered.
 if re.search(r'\b(OPTIONAL|UNION|SERVICE|MINUS|EXISTS|GROUP\s+BY)\b',query,re.I):return out
 triples=[];extends=[];filters=[]
 def walk(x):
  if hasattr(x,'name'):
   if x.name=='BGP':triples.extend(x['triples'])
   if x.name=='Extend':extends.append(x)
   if x.name=='Filter':filters.append(x)
   for v in x.values():walk(v)
  elif isinstance(x,(list,tuple)):
   for v in x:walk(v)
 def variables(x):
  if isinstance(x,Variable):return {str(x)}
  if hasattr(x,'values'):return set().union(*(variables(v) for v in x.values())) if len(x) else set()
  if isinstance(x,(list,tuple,set)):return set().union(*(variables(v) for v in x)) if x else set()
  return set()
 walk(algebra);bound={'this'}|variables(triples)
 for x in reversed(extends):
  missing=variables(x['expr'])-bound
  if missing:out.append(finding(c,'SPARQL_ERROR','Unbound BIND operand: '+','.join(sorted(missing)),query,expected='Every operand bound before use',evidence=evidence,suggestion='Bind the intended operand from the explicit schema path before this BIND.',location='sh:select/BIND'))
  bound.add(str(x['var']))
 for x in filters:
  missing=variables(x['expr'])-bound
  # BOUND/!BOUND intentionally tests missing values; skip those variables, preserve limited scope.
  missing-={v for v in re.findall(r'\bBOUND\s*\(\s*[?$](\w+)\s*\)',query,re.I)}
  if missing:out.append(finding(c,'SPARQL_ERROR','Unbound FILTER operand: '+','.join(sorted(missing)),query,expected='Bound comparison operands',evidence=evidence,suggestion='Use the bound variable or add the source-backed operand path.',location='sh:select/FILTER'))
 return out

def check(c,schema,rid):
 out=[]
 for issue in schema.context_issues.get(rid,[]):out.append(finding(c,'UNRESOLVED_CONTEXT','Source context requires reconciliation',issue['excerpt'],expected=issue['disposition'],evidence=json.dumps(issue),suggestion='Resolve the source/contract exception before judging or repairing code.',location='source '+issue['source_clause'],confirmed=False))
 try:g=Graph().parse(data=c.code,format='turtle')
 except Exception as e:
  match=re.search(r'at line (\d+)',str(e));line=int(match.group(1)) if match else None
  excerpt=c.code.splitlines()[line-1] if line and line<=len(c.code.splitlines()) else c.code
  return [finding(c,'PARSE_ERROR','Turtle parse failed',excerpt,evidence='rdflib Turtle parser',suggestion='Correct only the reported syntax.',location='Turtle parser'+(' line '+str(line) if line else ''),diagnostic=str(e))]
 ids={str(x) for triple in g for x in triple if isinstance(x,URIRef)}
 for q in g.objects(None,SH.select):ids|=iri_tokens(str(q))
 for i in sorted(ids):
  if i.startswith(str(N)) and i not in schema.canonical or i.startswith(str(U)) and i not in schema.units or i.startswith(str(Q)) and i not in {str(Q.unit),str(Q.numericValue),str(Q.QuantityValue)}:
   local=re.split(r'[/#]',i)[-1];matches=[u for u in schema.canonical if re.split(r'[/#]',u)[-1]==local]
   out.append(finding(c,'CANONICAL_IDENTIFIER_ERROR','Identifier absent from locked canonical metadata',i,expected=matches[0] if len(matches)==1 else 'An evidenced canonical identifier; no inferred replacement',evidence='schema/term_registry.json exact iri/unitIri; schema/Schema_for_NLTL.ttl',suggestion=('Replace only the namespace/identifier with '+matches[0]+'; preserve values.') if len(matches)==1 else 'Resolve against source metadata; do not guess.',location='IRI '+i))
 def pathitems(node):
  if isinstance(node,URIRef):return [str(node)]
  try:return [str(x) for x in Collection(g,node)] if (node,RDF.first,None) in g else None
  except Exception:return None
 root,allowed=schema.allowed_paths(rid)
 owner_contract=schema.index['termOwners'].get(rid,{})
 def property_checks(ps,path):
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
     out.append(finding(c,'PATH_CONTRACT_ERROR','Complete property path conflicts with explicit ownership contract',' / '.join(path),expected=json.dumps(allowed[prop]),evidence=json.dumps(dict(termOwners=owner_contract,modelPaths=schema.index['dependencyContracts'].get(rid,{}).get('modelPaths',[]))),suggestion='Follow the evidenced complete path; preserve the remaining obligation.',location='sh:path '+prop))
    elif prop.startswith(str(N)) and 'Property' in schema.terms.get(prop,{}).get('kind','') and prop not in allowed:
     out.append(finding(c,'UNRESOLVED_CONTEXT','No explicit ownership/path contract for used property',prop,expected='Source-backed owner binding before path judgment',evidence='No termOwners entry; RDFS domain is not exclusive ownership',suggestion='Document and resolve representation evidence; do not assume ship.',location='owner '+prop,confirmed=False))
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
   else:out.append(finding(c,'UNRESOLVED_CONTEXT','Target cannot be bound to an explicit model owner',str(cls),expected=root,evidence='termOwners/modelPaths and rdfs:subClassOf closure',suggestion='Resolve target applicability from source and contract.',location='sh:targetClass',confirmed=False))
  else:visit(shape,[],set())
 for dtype in g.objects(None,SH.datatype):
  valid={'string','boolean','decimal','integer','int','long','short','byte','nonNegativeInteger','positiveInteger','nonPositiveInteger','negativeInteger','unsignedLong','unsignedInt','unsignedShort','unsignedByte','double','float','date','dateTime','time','duration','dayTimeDuration','yearMonthDuration','anyURI','normalizedString','token','language','Name','NCName','NMTOKEN','hexBinary','base64Binary','gYear','gMonth','gDay','gYearMonth','gMonthDay'}
  if not isinstance(dtype,URIRef) or str(dtype).startswith(str(XSD)) and str(dtype).removeprefix(str(XSD)) not in valid:
   out.append(finding(c,'TERM_KIND_ERROR','Unsupported or invalid datatype IRI',str(dtype),expected='Valid declared XML Schema/RDF datatype',evidence='XML Schema datatype vocabulary and locked metadata',suggestion='Use the declared property datatype.',location='sh:datatype'))
 for q in g.objects(None,SH.select):
  text=str(q);out+=sparql_checks(c,text)
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
 # RDF1.1 plain strings are xsd:string; no invented numeric/string coercions.
 unique={f.key:f for f in out};return list(unique.values())

def obligation_signature(code):
 try:g=Graph().parse(data=code,format='turtle')
 except Exception:return set()
 sig=set()
 for p in g.objects(None,SH.path):
  if isinstance(p,URIRef):sig.add(('path',str(p)))
 for pred in [SH.datatype,SH['class'],SH.pattern,SH.minLength,SH.maxLength,SH.minCount,SH.maxCount,SH.minInclusive,SH.maxInclusive,SH.minExclusive,SH.maxExclusive,SH.hasValue,SH.targetClass,SH['in'],SH['or'],SH['and']]:
  for s,o in g.subject_objects(pred):
   path=g.value(s,SH.path); value='STRUCTURE' if isinstance(o,BNode) else o.n3();sig.add((str(pred),str(path or 'node'),value))
 for query in g.objects(None,SH.select):
  # Query changes are never silently accepted. Exact semantics require evidenced review.
  sig.add(('query',str(query)))
 return sig

def regression(previous,current,authorization=None):
 # A source-backed semantic correction may change exactly its cited excerpt. It cannot authorize unrelated deletions.
 removed=obligation_signature(previous.code)-obligation_signature(current.code)
 justified=[]
 for old in removed:
  text=old[-1]
  if authorization and any(f.category=='TERM_KIND_ERROR' and f.excerpt and f.excerpt in text and old[0]==str(SH.datatype) for f in authorization):justified.append(old)
  if authorization and any(f.category=='CANONICAL_IDENTIFIER_ERROR' and f.excerpt in text and f.expected.startswith(('http://','https://')) and text.replace(f.excerpt,f.expected) in {x[-1] for x in obligation_signature(current.code)} for f in authorization):justified.append(old)
  if authorization and any(f.category=='SOURCE_BACKED_LOGIC_ERROR' and f.confirmed and f.excerpt==text and f.evidence and f.suggestion for f in authorization):justified.append(old)
 removed-=set(justified)
 if not removed:return []
 return [finding(current,'SOURCE_BACKED_LOGIC_ERROR','Repair removed or changed an existing obligation/threshold/applicability',json.dumps(sorted(removed)),expected='Preserve prior obligations unless an exact source-backed correction discharges this change',evidence='Previous candidate '+previous.sha256+' vs '+current.sha256,suggestion='Restore the removed obligation or supply exact source-backed review for this change.',location='repair regression guard',diagnostic='REMOVED_OR_CHANGED '+json.dumps(sorted(removed)))]

def transitions(old,new):
 a={f.key for f in old};b={f.key for f in new}
 return dict(resolved=sorted(a-b),persistent=sorted(a&b),new=sorted(b-a))

def runtime_probe(c,schema):
 """Approved schema-derived synthetic empty targets; conformance is deliberately ignored."""
 from pyshacl import validate
 from .sparql_extensions import register_math_functions
 register_math_functions();g=Graph().parse(data=c.code,format='turtle');witness=Graph()
 for i,cls in enumerate(g.objects(None,SH.targetClass)):witness.add((URIRef('urn:nltlv2:approved-empty-target:'+str(i)),RDF.type,cls))
 try:
  _,report,_=validate(witness,shacl_graph=g,ont_graph=schema.graph,inference='rdfs',advanced=True,abort_on_first=False,meta_shacl=False)
  if not isinstance(report,Graph):raise RuntimeError(str(report))
  return [],dict(policy='Schema-derived synthetic empty targets only; never evaluation fixtures',ignored_conformance=True,witness=witness.serialize(format='turtle'))
 except Exception as e:
  return [finding(c,'SPARQL_ERROR','Local SHACL execution failed; not a conformance verdict',c.code,expected='Executable SHACL on approved synthetic development input',evidence='Schema-derived empty-target runtime probe',suggestion='Correct execution/binding structure without changing regulatory obligations.',location='local runtime',diagnostic=type(e).__name__+': '+str(e))],dict(error=type(e).__name__+': '+str(e),not_conformance=True)
