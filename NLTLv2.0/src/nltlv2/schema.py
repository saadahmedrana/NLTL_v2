"""Ontology/representation metadata and original source context only.
No compliance algorithms, case expectations or per-regulation solution profiles.
"""
import json,hashlib,copy
from collections import defaultdict
from rdflib import Graph,Namespace,URIRef,RDF,RDFS,OWL,XSD
from .core import load
N=Namespace('https://w3id.org/nltl/vocab#');Q=Namespace('http://qudt.org/schema/qudt/');U=Namespace('http://qudt.org/vocab/unit/')
TERM_FIELDS={'localName','iri','kind','label','datatype','parentOrRange','unitIri','unitSymbol','sourceRefs'}
class Schema:
 def __init__(self,project):
  self.project=project;self.graph=Graph().parse(project.path('schema/Schema_for_NLTL.ttl'))
  self.registry=[{k:v for k,v in r.items() if k in TERM_FIELDS} for r in load(project.path('schema/term_registry.json'))]
  self.terms={r['iri']:r for r in self.registry};self.ontology_terms={str(s) for s in self.graph.subjects() if isinstance(s,URIRef)}
  for kind,rdfkind in [('ObjectProperty',OWL.ObjectProperty),('DatatypeProperty',OWL.DatatypeProperty)]:
   for prop in self.graph.subjects(RDF.type,rdfkind):
    if str(prop) in self.terms:continue
    ranges=list(self.graph.objects(prop,RDFS.range));row=dict(localName=str(prop).split('#')[-1],iri=str(prop),kind=kind,parentOrRange=str(ranges[0]) if len(ranges)==1 else '',datatype=str(ranges[0]) if kind=='DatatypeProperty' and len(ranges)==1 and str(ranges[0]).startswith(str(XSD)) else '',mapping_basis='Explicit ontology declaration; no inferred regulatory obligation')
    self.terms[str(prop)]=row;self.registry.append(row)
  self.units={r['unitIri'] for r in self.registry if r.get('unitIri')};self.canonical=set(self.terms)|self.ontology_terms|self.units|{str(Q.numericValue),str(Q.unit),str(Q.QuantityValue)}
  self.bindings=load(project.path('schema/representation_bindings.json'))['requirements']
  for rid,b in self.bindings.items():
   if set(b)-{'terms','owners','model_paths','target_owner'}:raise ValueError('NON_REPRESENTATION_MAPPING_FIELD '+rid)
   for edge in b.get('model_paths',[]):
    if set(edge)!={'fromOwner','toOwner','via'}:raise ValueError('INVALID_REPRESENTATION_EDGE')
  self.requirements=load(project.path('data/requirements/requirements.json'));self.catalog=load(project.path('data/requirements/source_catalog.json'))['sources']
  context=load(project.path('schema/locked_representation_context.jsonld'))['@context']
  encoding=context.get('numericValue',{}).get('@type');prefix,local=encoding.split(':',1)
  ns=context[prefix];ns=ns['@id'] if isinstance(ns,dict) else ns
  self.quantity_profile=dict(file='schema/locked_representation_context.jsonld',canonical_literal_encoding=ns+local,scope='Declared quantity serialization; no new global ontology range or numeric-equality solution')
  self.context_issues={} # Generic interface; no per-requirement interpretation overrides.
 def subtype(self,child,parent):return child==parent or parent in self.graph.transitive_objects(child,RDFS.subClassOf)
 def effective_owners(self,rid):return copy.deepcopy(self.bindings.get(rid,{}).get('owners',{}))
 def allowed_paths(self,rid):
  b=self.bindings.get(rid,{});owners=b.get('owners',{});edges=b.get('model_paths',[]);root=b.get('target_owner')
  if not root:
   roots={e['fromOwner'] for e in edges}-{e['toOwner'] for e in edges}
   if len(roots)==1:root=next(iter(roots))
   elif len(set(owners.values()))==1:root=next(iter(owners.values()))
  allowed={}
  for prop,owner in owners.items():
   routes=[];queue=[(root,[],set())] if root else []
   while queue:
    at,path,seen=queue.pop()
    if self.subtype(N[owner],N[at]):routes.append(tuple(path+[str(N[prop])]))
    for edge in edges:
     key=(edge['fromOwner'],edge['via'],edge['toOwner'])
     if key not in seen and self.subtype(N[edge['fromOwner']],N[at]) and len(path)<len(edges):queue.append((edge['toOwner'],path+[str(N[edge['via']])],seen|{key}))
   allowed[str(N[prop])]=sorted(set(routes))
  return root,allowed
 def documents(self,record):
  entry={'file':record['source_file'],'sha256':record.get('source_sha256')} if record.get('source_file') else self.catalog.get(record.get('source'))
  if not entry:raise ValueError('AUTHORITATIVE_SOURCE_DOCUMENT_REQUIRED')
  docs=[]
  for item in [entry]+record.get('supporting_sources',[]):
   if set(item)-{'file','sha256'}:raise ValueError('INVALID_SOURCE_DOCUMENT_DESCRIPTOR')
   file=self.project.path(item['file']);raw=file.read_bytes();actual=hashlib.sha256(raw).hexdigest()
   if item.get('sha256') and item['sha256']!=actual:raise ValueError('SOURCE_DOCUMENT_HASH_MISMATCH')
   text=raw.decode('utf-8')
   if not text.strip():raise ValueError('EMPTY_SOURCE_DOCUMENT')
   docs.append(dict(file=item['file'],sha256=actual,text=text,authority='User-supplied retained source document; interpretations are not independently verified'))
  return docs
 def context(self,rid):
  raw=self.requirements[rid];record={k:copy.deepcopy(raw[k]) for k in ['id','source','clause','text'] if k in raw}
  if not all(record.get(k) for k in ['id','clause','text']):raise ValueError('REQUIREMENT_ID_CLAUSE_TEXT_REQUIRED')
  docs=self.documents(raw);b=copy.deepcopy(self.bindings.get(rid,{}));terms=b.get('terms',[])
  rows=[copy.deepcopy(r) for r in self.registry if not terms or r['localName'] in terms]
  # Ontology infrastructure and named values remain genuine declarations even if
  # not duplicated in the registry; never turn a class into a closed-value list.
  subjects={URIRef(r['iri']) for r in rows}|{N[x] for x in terms}|{N[o] for o in b.get('owners',{}).values()}
  if not terms:subjects|={s for s in self.graph.subjects() if isinstance(s,URIRef)}
  for subject in list(subjects):subjects.update(self.graph.transitive_objects(subject,RDFS.subClassOf))
  evidence=sorted([[s.n3(),p.n3(),o.n3()] for s in subjects for p,o in self.graph.predicate_objects(s)])
  examples=[] # Curated solution examples are offline-only, not production dependencies.
  return dict(requirement=record,source_documents=docs,schema_terms=rows,ontology_evidence=evidence,termOwners=b.get('owners',{}),modelPaths=b.get('model_paths',[]),contract={'kind':'REPRESENTATION_ONLY','owners':b.get('owners',{}),'modelPaths':b.get('model_paths',[]),'target_owner':b.get('target_owner')},unresolvedOwnership=[r['localName'] for r in rows if 'Property' in r.get('kind','') and r['localName'] not in b.get('owners',{})],unresolvedSourceContext=[],examples=examples,scope='Implement and review the supplied source in the declared schema. No supplied compliance solution or expected verdict. Unspecified representation/applicability remains uncertain.',source_completeness='Frozen excerpt is not a proof of complete context; full retained source is included for review.',quantityEncoding=self.quantity_profile)
 def audit(self):
  return dict(status='PARSED_REPRESENTATION_ONLY',ontology_triples=len(self.graph),registry_terms=len(self.registry),requirements=len(self.requirements),representation_mappings=len(self.bindings),source_documents=len(self.catalog),domains_are_not_exclusive_owners=True,regulatory_correctness_certified=False,solution_profiles_loaded=False)
