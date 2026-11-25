"""Ontology/representation metadata and original source context only.
No compliance algorithms, case expectations or per-regulation solution profiles.
"""
import json,hashlib,copy
from collections import defaultdict
from rdflib import Graph,Namespace,URIRef,RDF,RDFS,OWL,XSD,SKOS
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
  if not isinstance(context.get('numericValue'),dict) or not context['numericValue'].get('@id') or not context['numericValue'].get('@type'):raise ValueError('QUANTITY_NUMERIC_DECLARATION_REQUIRED')
  if not isinstance(context.get('unit'),dict) or not context['unit'].get('@id') or context['unit'].get('@type')!='@id':raise ValueError('QUANTITY_UNIT_DECLARATION_REQUIRED')
  encoding=context['numericValue']['@type'];prefix,local=encoding.split(':',1)
  ns=context[prefix];ns=ns['@id'] if isinstance(ns,dict) else ns
  def expand(value):
   if value.startswith(('http:','https:')):return value
   prefix,local=value.split(':',1);entry=context[prefix];return (entry['@id'] if isinstance(entry,dict) else entry)+local
  numeric=context.get('numericValue',{})
  unit=context['unit']
  self.quantity_profile=dict(file='schema/locked_representation_context.jsonld',numeric_predicate=expand(numeric['@id']),unit_predicate=expand(unit['@id']),canonical_literal_encoding=ns+local,quantity_class=str(Q.QuantityValue),declarations={'numericValue':numeric,'unit':unit},scope='Declared quantity serialization, not a numeric-equality solution or conversion')
  # Projection of genuine JSON-LD declarations; never edit ontology triples.
  for iri,kind,dt in [(self.quantity_profile['numeric_predicate'],'DatatypeProperty',ns+local),(self.quantity_profile['unit_predicate'],'ObjectProperty','')]:
   if iri not in self.terms:
    row=dict(iri=iri,localName=iri.rsplit('/',1)[-1],kind=kind,datatype=dt,mapping_basis='Declared JSON-LD '+self.quantity_profile['file'],declaration_evidence=self.quantity_profile['declarations']);self.terms[iri]=row;self.registry.append(row)
  for subject in sorted(self.ontology_terms):
   if subject in self.terms:continue
   node=URIRef(subject);types=set(self.graph.objects(node,RDF.type));kind='Class' if types & {OWL.Class,RDFS.Class} else 'NamedIndividual' if types else 'DeclaredTerm'
   labels=sorted(str(x) for p in [RDFS.label,SKOS.prefLabel] for x in self.graph.objects(node,p))
   row=dict(iri=subject,localName=subject.rsplit('#',1)[-1].rsplit('/',1)[-1],kind=kind,label='; '.join(labels),types=sorted(map(str,types)),mapping_basis='Ontology declaration (registry row not required)');self.terms[subject]=row;self.registry.append(row)
  self.canonical=set(self.terms)|self.ontology_terms|self.units|{str(Q.QuantityValue)}
  self.context_issues={};self.source_manifests={};self.document_cache={}
 def term_evidence(self,iri):
  node=URIRef(iri)
  return dict(term=self.terms.get(iri),ontology_triples=sorted([[node.n3(),p.n3(),o.n3()] for p,o in self.graph.predicate_objects(node)]),quantity_declaration=self.quantity_profile if iri in [self.quantity_profile['numeric_predicate'],self.quantity_profile['unit_predicate']] else None)
 def identifier_correction(self,iri):
  # A documented serialization identifier repair, not a regulatory solution or unit conversion.
  if iri==str(Q.value) and self.quantity_profile['numeric_predicate'] in self.terms:
   return self.quantity_profile['numeric_predicate'],self.term_evidence(self.quantity_profile['numeric_predicate'])
  local=iri.rsplit('#',1)[-1].rsplit('/',1)[-1];matches=[x for x in self.canonical if x.rsplit('#',1)[-1].rsplit('/',1)[-1]==local]
  return (matches[0],self.term_evidence(matches[0])) if len(matches)==1 else (None,dict(status='UNRESOLVED_IDENTIFIER',iri=iri))
 def closure(self,seeds):
  # Include ancestor evidence without reverse-expanding broad ancestors into every term.
  seen=set();expanded=set();queue=[(URIRef(x),True) for x in seeds]
  skip={OWL.Class,RDFS.Class,RDF.Property,OWL.ObjectProperty,OWL.DatatypeProperty,SKOS.Concept}
  while queue:
   node,members=queue.pop()
   if node not in seen:
    seen.add(node)
    for p in [RDFS.range,RDFS.domain,RDFS.subClassOf,OWL.equivalentClass,RDF.type,SKOS.broader]:
     queue.extend((x,p==RDFS.range) for x in self.graph.objects(node,p) if isinstance(x,URIRef))
   if members and node not in expanded and node not in skip and not str(node).startswith(str(XSD)):
    expanded.add(node)
    queue.extend((x,False) for x in self.graph.subjects(RDF.type,node) if isinstance(x,URIRef))
    queue.extend((x,True) for x in self.graph.subjects(RDFS.subClassOf,node) if isinstance(x,URIRef))
  return seen
 def source_evidence(self,file,document_sha256,start,end):
  from .source_context import retrieve
  return retrieve(self.project,file,document_sha256,start,end)
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
  entry={k:entry[k] for k in ['file','sha256'] if k in entry}
  docs=[]
  for item in [entry]+record.get('supporting_sources',[]):
   if set(item)-{'file','sha256'}:raise ValueError('INVALID_SOURCE_DOCUMENT_DESCRIPTOR')
   file=self.project.path(item['file']);raw=file.read_bytes();actual=hashlib.sha256(raw).hexdigest()
   if item.get('sha256') and item['sha256']!=actual:raise ValueError('SOURCE_DOCUMENT_HASH_MISMATCH')
   text=raw.decode('utf-8')
   if not text.strip():raise ValueError('EMPTY_SOURCE_DOCUMENT')
   doc=dict(file=item['file'],sha256=actual,text=text,authority='User-supplied retained source document; interpretations are not independently verified');docs.append(doc);self.document_cache[item['file']]=doc
  return docs
 def context(self,rid):
  raw=self.requirements[rid];record={k:copy.deepcopy(raw[k]) for k in ['id','source','clause','text'] if k in raw}
  if not all(record.get(k) for k in ['id','clause','text']):raise ValueError('REQUIREMENT_ID_CLAUSE_TEXT_REQUIRED')
  originals=self.documents(raw)
  from .source_context import select_document
  docs=[];manifests=[]
  for i,document in enumerate(originals):
   fragments,manifest=select_document(document,record,supporting=i>0);docs+=fragments;manifests.append(manifest)
  self.source_manifests[rid]=manifests
  b=copy.deepcopy(self.bindings.get(rid,{}));terms=b.get('terms',[])
  seedrows=[r for r in self.registry if not terms or r['localName'] in terms]
  seeds={r['iri'] for r in seedrows}|{str(N[x]) for x in terms}|{str(N[o]) for o in b.get('owners',{}).values()}
  seeds|={self.quantity_profile[k] for k in ['numeric_predicate','unit_predicate','quantity_class']}|{r['unitIri'] for r in seedrows if r.get('unitIri')}
  subjects=self.closure(seeds)
  rows=[copy.deepcopy(r) for r in self.registry if URIRef(r['iri']) in subjects]
  evidence=sorted([[s.n3(),p.n3(),o.n3()] for s in subjects for p,o in self.graph.predicate_objects(s)])
  unresolved=[dict(file=m['file'],reference=r) for m in manifests for r in m['unresolved_references']]
  manifest_hash=hashlib.sha256(json.dumps(manifests,sort_keys=True).encode()).hexdigest()
  return dict(requirement=record,source_documents=docs,source_selection=dict(manifest_sha256=manifest_hash,included_characters=sum(m['included_characters'] for m in manifests),original_characters=sum(m['original_characters'] for m in manifests),omitted_sections=sum(not p['included'] for m in manifests for p in m['sections']),retrieval='Schema.source_evidence(file, document_sha256, start, end); complete sections/hashes retained in source_selection_manifest.json; missing necessary evidence must remain unresolved'),schema_terms=rows,ontology_evidence=evidence,termOwners=b.get('owners',{}),modelPaths=b.get('model_paths',[]),contract={'kind':'REPRESENTATION_ONLY','owners':b.get('owners',{}),'modelPaths':b.get('model_paths',[]),'target_owner':b.get('target_owner')},unresolvedOwnership=[r['localName'] for r in rows if 'Property' in r.get('kind','') and r['localName'] not in b.get('owners',{}) and not r['iri'].startswith(str(Q))],unresolvedSourceContext=unresolved,examples=[],scope='Implement and review the supplied source in the declared schema. No supplied compliance solution or expected verdict. Material unspecified representation/applicability prevents acceptance.',source_completeness='Deterministic source selection, not a proof of complete context. Ambiguous primary anchors retain full source; unresolved references require review.',quantityEncoding=self.quantity_profile)
 def audit(self):
  return dict(status='PARSED_REPRESENTATION_ONLY',ontology_triples=len(self.graph),registry_terms=len(self.registry),requirements=len(self.requirements),representation_mappings=len(self.bindings),source_documents=len(self.catalog),domains_are_not_exclusive_owners=True,regulatory_correctness_certified=False,solution_profiles_loaded=False)
