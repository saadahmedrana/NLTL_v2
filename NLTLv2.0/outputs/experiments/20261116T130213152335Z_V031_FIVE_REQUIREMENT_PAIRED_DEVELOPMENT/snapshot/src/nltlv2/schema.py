from __future__ import annotations
import json,collections,re
from rdflib import Graph,Namespace,URIRef,RDF,RDFS,OWL,XSD,Literal
from rdflib.namespace import SKOS
import hashlib,copy
from .core import load,digest
N=Namespace('https://w3id.org/nltl/vocab#');Q=Namespace('http://qudt.org/schema/qudt/');U=Namespace('http://qudt.org/vocab/unit/')
class Schema:
 def __init__(self,project):
  self.project=project;profile_data=load(project.path('data/contracts/development_preflight_profiles.json'));self.development_profiles=profile_data['requirements'];self.quantity_profile=profile_data['representation_context'];self.graph=Graph().parse(project.path('schema/Schema_for_NLTL.ttl'))
  self.registry=load(project.path('schema/term_registry.json'))
  self.controlled_registry=load(project.path('schema/controlled_value_registry.json'))
  self.enumeration_obligations=load(project.path('data/contracts/enumeration_obligations.json'))['requirements']
  self.validate_enumeration_contracts()
  self.registry+=list(self.controlled_registry['terms'].values())
  self.terms={r['iri']:r for r in self.registry};self.index=load(project.path('data/contracts/requirement_term_index.json'))
  self.requirements=load(project.path('data/requirements/requirements.json'));self.context_issues=load(project.path('data/contracts/context_issues.json'))
  self.validate_development_profiles()
  self.units={r['unitIri'] for r in self.registry if r.get('unitIri')}
  self.ontology_terms={str(s) for s in self.graph.subjects() if isinstance(s,URIRef)}
  self.canonical=set(self.terms)|self.ontology_terms|self.units|{str(Q.numericValue),str(Q.unit),str(Q.QuantityValue)}
  from .development_checks import contracts
  self.development_witness_contracts=contracts(self)
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
 def effective_contract(self,rid):
  contract=copy.deepcopy({k:v for k,v in self.index['dependencyContracts'].get(rid,{}).items() if k not in ['observedFailureStatus','r6AuditDisposition','auditFlags']})
  profile=self.development_profiles.get(rid)
  if profile:
   contract.update(copy.deepcopy(profile.get('contract_patch',{})))
   contract['modelPaths']=copy.deepcopy(profile['model_paths'])
   contract['sourceBackedObligations']=copy.deepcopy(profile['obligations'])
   contract['verificationScope']=profile['scope']
   contract['sourceApplicabilityPrecondition']=profile['source_precondition']
   contract['sourceEvidence']=copy.deepcopy(profile['source'])
   contract['inactiveLegacyTerms']=copy.deepcopy(profile['inactive_terms'])
   contract['coverageClaim']=profile['logical_coverage_claim']
   witness=self.development_witness_contracts.get(rid) if hasattr(self,'development_witness_contracts') else None
   if witness:
    contract['developmentVerification']=dict(operation=witness['operation'],fields=copy.deepcopy(witness['fields']),readiness_policy=witness['readiness_policy'],scope=witness['scope'],limits=witness['limits'],complete_verification=False,provenance=witness['provenance'])
   if profile.get('blocking_issues'):
    contract['lockedMetadataStatus']=contract.get('status')
    contract['status']='BLOCKED_APPLICABILITY_BINDING'
    contract['preflightBlockers']=copy.deepcopy(profile['blocking_issues'])
  return contract
 def effective_owners(self,rid):
  owners=self.index['termOwners'].get(rid,{})
  profile=self.development_profiles.get(rid)
  return {k:v for k,v in owners.items() if not profile or k in profile['active_terms']}
 def validate_development_profiles(self):
  representation=self.project.path(self.quantity_profile['file'])
  if hashlib.sha256(representation.read_bytes()).hexdigest()!=self.quantity_profile['sha256']:raise ValueError('Locked representation profile hash mismatch')
  context=load(representation)['@context']
  if context['numericValue']!={'@id':'qudt:numericValue','@type':'xsd:decimal'}:raise ValueError('Numeric representation context changed')
  def expand(curie):
   prefix,local=curie.split(':',1);namespace=context[prefix]
   return (namespace['@id'] if isinstance(namespace,dict) else namespace)+local
  if self.quantity_profile['canonical_literal_encoding']!=expand(context['numericValue']['@type']) or self.quantity_profile['numeric_value_predicate']!=expand(context['numericValue']['@id']) or self.quantity_profile['unit_predicate']!=expand(context['unit']['@id']):raise ValueError('Invented datatype/predicate binding in quantity profile')
  for name,row in self.controlled_registry['terms'].items():
   iri=URIRef(row['iri']);parent=URIRef(row['parentOrRange']);source=row['source_evidence'];file=self.project.path(source['file'])
   if (iri,RDF.type,parent) not in self.graph or row['label'] not in [str(x) for x in self.graph.objects(iri,SKOS.prefLabel)]:raise ValueError('Unverified supplemental controlled value '+name)
   if hashlib.sha256(file.read_bytes()).hexdigest()!=source['sha256'] or source['exact_excerpt'] not in file.read_text() or row['label'] not in source['exact_excerpt']:raise ValueError('Stale or unsupported controlled-value source evidence')
  for rid,profile in self.development_profiles.items():
   declared={item['code'] for item in profile.get('blocking_issues',[])}
   enforced={item['code'] for item in self.context_issues.get(rid,[]) if item.get('blocking_before_generation')}
   if not declared<=enforced:raise ValueError('Source applicability blocker not enforced before generation: '+rid)
   source=profile['source'];file=self.project.path(source['file']);owner=profile['term_owner_evidence']
   if hashlib.sha256(file.read_bytes()).hexdigest()!=source['sha256'] or source['exact_excerpt'] not in file.read_text():raise ValueError('Stale development source: '+rid)
   if owner['owners']!=self.index['termOwners'][rid] or hashlib.sha256(self.project.path(owner['file']).read_bytes()).hexdigest()!=owner['sha256']:raise ValueError('Unverified owner evidence: '+rid)
   if set(profile['active_terms']) & set(profile['inactive_terms']):raise ValueError('Term both active and quarantined')
   for term in profile['active_terms']:
    if not any(self.graph.triples((N[term],None,None))):raise ValueError('Unknown active schema term '+term)
   for edge in profile['model_paths']:
    if self.index['termOwners'][rid].get(edge['via'])!=edge['fromOwner'] or (N[edge['via']],RDFS.range,N[edge['toOwner']]) not in self.graph:raise ValueError('Unverified model path: '+rid)
  return {'requirements':sorted(self.development_profiles),'quantity_encoding':'xsd:decimal canonical JSON-LD encoding; no new global RDF range','status':'VERIFIED_CONTEXT_WITH_EXPLICIT_BLOCKERS'}
 def subtype(self,child,parent):return child==parent or parent in self.graph.transitive_objects(child,RDFS.subClassOf)
 def allowed_paths(self,rid):
  d=self.effective_contract(rid);owners=self.effective_owners(rid)
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
  req=copy.deepcopy(self.requirements[rid]);profile=self.development_profiles.get(rid);terms=list(profile['active_terms'] if profile else self.index['requirements'].get(rid,[]));owners=self.effective_owners(rid)
  obligations=self.enumeration_obligations.get(rid,[])
  terms+= [str(x['iri']).split('#')[-1] for o in obligations for x in o['members']]
  rows=copy.deepcopy([r for r in self.registry if r['localName'] in terms])
  for row in rows:
   correction=(profile or {}).get('term_reference_corrections',{}).get(row['localName'])
   if correction:row['original_sourceRefs']=row.get('sourceRefs');row['sourceRefs']=correction;row['source_reference_correction_evidence']=copy.deepcopy(profile['source'])
  # Indexed legacy terms without binding remain explicit unresolved context, never guessed.
  unbound=[r['localName'] for r in rows if 'Property' in r['kind'] and r['localName'] not in owners]
  examples=[json.loads(l) for l in self.project.path('data/examples/few_shot_pairs.jsonl').read_text().splitlines() if l.strip()][:2]
  contract=self.effective_contract(rid)
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
  result=dict(requirement=req,schema_terms=rows,ontology_evidence=evidence,unresolvedSourceContext=self.context_issues.get(rid,[]),contract=contract,termOwners=owners,modelPaths=contract.get('modelPaths',[]),unresolvedOwnership=unbound,examples=examples,scope='Locked representation only; unresolved ownership must not be invented. No evaluation inputs.')
  quantity_terms=[row for row in rows if row['kind']=='QuantityProperty']
  if quantity_terms:
   result['quantityEncoding']=dict(profile=copy.deepcopy(self.quantity_profile),properties=[dict(iri=row['iri'],object_range=row['parentOrRange'],unit_iri=row['unitIri'],numeric_value_predicate=str(Q.numericValue),canonical_numeric_datatype=self.quantity_profile['canonical_literal_encoding']) for row in quantity_terms],warning='Canonical JSON-LD decimal encoding, not an invented global datatype range or permission to relabel units.')
  return result
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
