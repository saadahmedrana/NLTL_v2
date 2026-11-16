from __future__ import annotations
import json,collections,re
from rdflib import Graph,Namespace,URIRef,RDF,RDFS,OWL,XSD,Literal
from rdflib.namespace import SKOS
import hashlib,copy
from .core import load,digest
N=Namespace('https://w3id.org/nltl/vocab#');Q=Namespace('http://qudt.org/schema/qudt/');U=Namespace('http://qudt.org/vocab/unit/')
class Schema:
 def __init__(self,project):
  self.project=project;self.graph=Graph().parse(project.path('schema/Schema_for_NLTL.ttl'))
  self.registry=load(project.path('schema/term_registry.json'))
  self.controlled_registry=load(project.path('schema/controlled_value_registry.json'))
  self.enumeration_obligations=load(project.path('data/contracts/enumeration_obligations.json'))['requirements']
  self.validate_enumeration_contracts()
  self.registry+=list(self.controlled_registry['terms'].values())
  self.terms={r['iri']:r for r in self.registry};self.index=load(project.path('data/contracts/requirement_term_index.json'))
  self.requirements=load(project.path('data/requirements/requirements.json'));self.context_issues=load(project.path('data/contracts/context_issues.json'))
  self.units={r['unitIri'] for r in self.registry if r.get('unitIri')}
  self.ontology_terms={str(s) for s in self.graph.subjects() if isinstance(s,URIRef)}
  self.canonical=set(self.terms)|self.ontology_terms|self.units|{str(Q.numericValue),str(Q.unit),str(Q.QuantityValue)}
 def validate_enumeration_contracts(self):
  """Fail closed on broken source, schema or supplemental-registry bindings."""
  locked_iris={row['iri'] for row in load(self.project.path('schema/term_registry.json'))}
  for rid,obligations in self.enumeration_obligations.items():
   for obligation in obligations:
    owner=obligation['owner_evidence'];locked=load(self.project.path(owner['file']))
    if obligation['requirement_id']!=rid or obligation['target_class']!=str(N.ship) or obligation['path']!=[str(N.iceClass)] or locked['termOwners'][rid].get('iceClass')!='ship':raise ValueError('Unverified enumeration owner/path contract')
    source=obligation['source'];file=self.project.path(source['file'])
    if hashlib.sha256(file.read_bytes()).hexdigest()!=source['sha256'] or source['exact_excerpt'] not in file.read_text():raise ValueError('Enumeration source evidence is stale or absent: '+rid)
    iris=[x['iri'] for x in obligation['members']]
    if len(iris)!=len(set(iris)) or len(iris)!=6:raise ValueError('Duplicate/incomplete TRF-010 value binding')
    for member in obligation['members']:
     iri=URIRef(member['iri']);row=self.controlled_registry['terms'][str(iri).split('#')[-1]]
     if row['iri']!=str(iri) or (iri,RDF.type,N.iceClassValue) not in self.graph or member['source_label'] not in [str(x) for x in self.graph.objects(iri,SKOS.prefLabel)]:raise ValueError('Unverified canonical value IRI: '+str(iri))
     registry=row['locked_registry_verification']
     if hashlib.sha256(self.project.path(registry['file']).read_bytes()).hexdigest()!=registry['sha256']:raise ValueError('Locked registry verification is stale')
     if registry['status']!=('PRESENT' if str(iri) in locked_iris else 'ABSENT'):raise ValueError('Incorrect locked registry membership assertion')
     if f"{member['source_ordinal']}. ice class {member['source_label']};" not in source['exact_excerpt']:raise ValueError('Source class/value binding absent')
  return {'status':'VERIFIED', 'requirements':sorted(self.enumeration_obligations),'supplemental_values':len(self.controlled_registry['terms'])}
 def subtype(self,child,parent):return child==parent or parent in self.graph.transitive_objects(child,RDFS.subClassOf)
 def allowed_paths(self,rid):
  d=self.index['dependencyContracts'].get(rid,{});owners=self.index['termOwners'].get(rid,{})
  root=self.index['requirementTargetOwner'].get(rid)
  if not root:
   # Only infer a unique root from an explicit directed model; never fallback to ship.
   edges=d.get('modelPaths',[]);orig={x['fromOwner'] for x in edges};dest={x['toOwner'] for x in edges};roots=orig-dest
   if len(roots)==1:root=next(iter(roots))
   elif len(set(owners.values()))==1:root=next(iter(owners.values()))
  routes={root:[()]} if root else {}
  for _ in range(len(d.get('modelPaths',[]))+1):
   for e in d.get('modelPaths',[]):
    for path in list(routes.get(e['fromOwner'],[])):
     route=path+(str(N[e['via']]),)
     if len(route)<=len(d.get('modelPaths',[])) and route not in routes.setdefault(e['toOwner'],[]):routes[e['toOwner']].append(route)
  return root,{str(N[p]):[x+(str(N[p]),) for x in routes.get(owner,[])] for p,owner in owners.items()}
 def context(self,rid):
  req=copy.deepcopy(self.requirements[rid]);terms=list(self.index['requirements'].get(rid,[]));owners=self.index['termOwners'].get(rid,{})
  obligations=self.enumeration_obligations.get(rid,[])
  terms+= [str(x['iri']).split('#')[-1] for o in obligations for x in o['members']]
  rows=[r for r in self.registry if r['localName'] in terms]
  # Indexed legacy terms without binding remain explicit unresolved context, never guessed.
  unbound=[r['localName'] for r in rows if 'Property' in r['kind'] and r['localName'] not in owners]
  examples=[json.loads(l) for l in self.project.path('data/examples/few_shot_pairs.jsonl').read_text().splitlines() if l.strip()][:2]
  contract={k:v for k,v in self.index['dependencyContracts'].get(rid,{}).items() if k not in ['observedFailureStatus','r6AuditDisposition','auditFlags']}
  contract=copy.deepcopy(contract)
  if obligations:
   contract['enumerationObligations']=copy.deepcopy(obligations)
   contract['verificationScope']='Assigned ice-class category membership only; the source descriptions do not create independent engineering qualification checks in this represented requirement.'
   contract['controlledValueTerms']=[str(x['iri']).split('#')[-1] for o in obligations for x in o['members']]
   contract['controlledValueMappings']=[copy.deepcopy(x) for o in obligations for x in o['members']]
   contract['cardinalityReview']=copy.deepcopy(obligations[0]['cardinality_review'])
  evidence_subjects={URIRef(r['iri']) for r in rows}|{N[o] for o in owners.values()}|{URIRef(r['unitIri']) for r in rows if r.get('unitIri')}
  evidence_subjects|={URIRef(row['parentOrRange']) for row in rows if row.get('parentOrRange','').startswith(('http://','https://'))}
  for subject in list(evidence_subjects):evidence_subjects.update(self.graph.transitive_objects(subject,RDFS.subClassOf))
  evidence=sorted([[s.n3(),p.n3(),o.n3()] for s in evidence_subjects for p,o in self.graph.predicate_objects(s) if p in [RDF.type,RDFS.domain,RDFS.range,RDFS.subClassOf,SKOS.prefLabel]])
  return dict(requirement=req,schema_terms=rows,ontology_evidence=evidence,unresolvedSourceContext=self.context_issues.get(rid,[]),contract=contract,termOwners=owners,modelPaths=self.index['dependencyContracts'].get(rid,{}).get('modelPaths',[]),unresolvedOwnership=unbound,examples=examples,scope='Locked representation only; unresolved ownership must not be invented. No evaluation inputs.')
 def audit(self):
  issues=[];counts=collections.Counter();kinds={'DatatypeProperty':OWL.DatatypeProperty,'ObjectProperty':OWL.ObjectProperty,'QuantityProperty':OWL.ObjectProperty}
  for r in self.registry:
   s=URIRef(r['iri']);counts[r['kind']]+=1
   if not any(self.graph.triples((s,None,None))):issues.append(dict(term=r['iri'],issue='REGISTRY_TERM_WITHOUT_ONTOLOGY_SUBJECT'))
   if r['kind'] in kinds and (s,RDF.type,kinds[r['kind']]) not in self.graph:issues.append(dict(term=r['iri'],issue='PROPERTY_KIND_REQUIRES_REVIEW',expected=str(kinds[r['kind']])))
   dt=r.get('datatype','')
   if dt:
    uri=URIRef(dt.replace('xsd:',str(XSD)))
    if r['kind']=='DatatypeProperty' and uri not in self.graph.objects(s,RDFS.range):issues.append(dict(term=r['iri'],issue='DATATYPE_RANGE_METADATA_DISAGREEMENT',datatype=str(uri),ranges=list(map(str,self.graph.objects(s,RDFS.range)))))
   if r.get('unitIri') and not r['unitIri'].startswith(str(U)) and (URIRef(r['unitIri']),RDF.type,Q.Unit) not in self.graph:issues.append(dict(term=r['iri'],issue='UNIT_METADATA_WITHOUT_DECLARATION',value=r['unitIri']))
  unresolved=[];conflicts=[]
  for rid,terms in self.index['requirements'].items():
   owners=self.index['termOwners'].get(rid,{})
   for p in terms:
    r=self.terms.get(str(N[p]),{})
    if 'Property' in r.get('kind','') and p not in owners:unresolved.append(dict(requirement=rid,property=p,reason='NO_EXPLICIT_TERM_OWNER; domain not exclusive'))
   for p,owner in owners.items():
    prop=N[p];dom=list(self.graph.objects(prop,RDFS.domain))
    # Record disjoint typing only. A broad or different domain alone is not contradiction.
    if any((N[owner],OWL.disjointWith,d) in self.graph or (d,OWL.disjointWith,N[owner]) in self.graph for d in dom):conflicts.append(dict(requirement=rid,property=p,owner=owner,domains=list(map(str,dom))))
  missingrefs=sorted({str(o) for s,p,o in self.graph if isinstance(o,URIRef) and str(o).startswith(str(N)) and not any(self.graph.triples((o,None,None)))})
  return dict(status='REVIEWED_NOT_FINAL',triples=len(self.graph),property_kinds=dict(counts),issues=issues,undefined_internal_references=missingrefs,unresolved_ownership=unresolved,explicit_disjoint_contract_conflicts=conflicts,notes=['Domains are typing assertions, not exclusive placement constraints.','Ownership rules use termOwners/modelPaths only.','No ontology RDF triples were changed.'])
