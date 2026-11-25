"""Shared caller admission: identity, provenance and boundary validation, never eligibility inference."""
import json,hashlib,re,copy
from urllib.parse import urlsplit
from rdflib import Graph,URIRef,Literal,RDF,RDFS,OWL
from rdflib.namespace import SH
from .core import finding
POLICY=dict(interpretation='A',external_responsibilities=['synthetic research-population eligibility assumption','applicable source-edition selection and construction-date eligibility'],constraint_responsibilities=['represented requirement obligations','conditions within the represented requirement','declared datatypes units and paths','effective activation within admitted population','complete query and logical correctness'],no_eligibility_inferred_from_missing_assertions=True,caller_attestation_is_not_independent_certification=True)
FIELDS={'format_version','admission_id','interpretation','population_description','focus_set','eligibility_assertion','provenance','source_editions','approval'}
def checksum(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def iri(value):
 if not isinstance(value,str) or any(c.isspace() or c in '<>\"{}|^`\\' for c in value) or value.startswith('_:'):return False
 try:return bool(urlsplit(value).scheme)
 except ValueError:return False
def text(value):return isinstance(value,str) and bool(value.strip()) and not re.search(r'(?i)\b(TODO|TBD|PLACEHOLDER)\b|[<>]',value)
def definition_hash(value):
 """Freeze scope/edition meaning independently of later approval metadata."""
 definition={k:copy.deepcopy(value.get(k)) for k in ['format_version','admission_id','interpretation','population_description','focus_set','eligibility_assertion']}
 definition['source_editions']=[{k:e.get(k) for k in ['document_id','edition','file','sha256']} for e in value.get('source_editions',[])]
 return checksum(definition)

def validate_declaration(value,schema,rid):
 errors=[];hashes={}
 def error(path,message):errors.append(dict(path=path,message=message))
 if not isinstance(value,dict) or set(value)!=FIELDS:return dict(status='UNRESOLVED_ADMISSION',valid=False,errors=[dict(path='$',message='Exactly '+', '.join(sorted(FIELDS))+' required')],input_hashes={})
 if type(value['format_version']) is not int or value['format_version']!=2 or value['interpretation']!='A':error('$','Supported format_version=2 and interpretation=A required')
 for key in ['admission_id','population_description']:
  if not text(value[key]):error('$.'+key,'Explicit non-placeholder caller declaration required')
 if value['eligibility_assertion']!='ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY':error('$.eligibility_assertion','Caller must explicitly assert ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY; no default/absence inference')
 provenance=value['provenance']
 if not isinstance(provenance,dict) or set(provenance)!={'declarant','reference','basis'}:error('$.provenance','declarant, reference and basis required')
 else:
  for k,v in provenance.items():
   if not text(v):error('$.provenance.'+k,'Non-placeholder caller provenance required')
 focus=value['focus_set']
 approval=value['approval']
 if not isinstance(approval,dict) or set(approval)!={'status','approved_by','reference'}:error('$.approval','Explicit status, approved_by, reference required')
 elif approval['status']!='APPROVED' or not text(approval['approved_by']) or not text(approval['reference']):error('$.approval','Scope requires actual caller approval with provenance; a proposal is never executable approval')
 if not isinstance(focus,dict) or set(focus)!={'mode','owner_class'}:error('$.focus_set','Exactly mode and owner_class allowed. Node/case identities belong only to the independent evaluation binding')
 else:
  if focus['mode']!='COMPLETE_CLASS_POPULATION_PER_INPUT':error('$.focus_set.mode','COMPLETE_CLASS_POPULATION_PER_INPUT is the supported common boundary')
  owner=focus['owner_class']
  if not iri(owner) or not any((URIRef(owner),RDF.type,c) in schema.graph for c in [OWL.Class,RDFS.Class]):error('$.focus_set.owner_class','Explicit declared representation class required; no regulatory eligibility is derived from it')
 editions=value['source_editions'];catalog=schema.catalog;seen=set();primary=schema.requirements.get(rid,{})
 principal=primary.get('source_file') or catalog.get(primary.get('source'),{}).get('file');primary_pinned=False
 if not isinstance(editions,list) or not editions:error('$.source_editions','Caller-selected source editions and selection provenance required')
 else:
  for i,e in enumerate(editions):
   path='$.source_editions['+str(i)+']'
   if not isinstance(e,dict) or set(e)!={'document_id','edition','file','sha256','selection_provenance'}:error(path,'document_id, edition, file, sha256, selection_provenance required');continue
   if not all(text(e[k]) for k in e):error(path,'Every edition/provenance field must be explicit');continue
   if e['document_id'] in seen:error(path+'.document_id','Duplicate document selection');continue
   seen.add(e['document_id'])
   matches=[v for title,v in catalog.items() if e['document_id'] in [v.get('document_id'),title]+v.get('aliases',[])]
   exact=[v for v in matches if v.get('file')==e['file'] and v.get('edition')==e['edition'] and v.get('sha256')==e['sha256']]
   if len(exact)!=1:error(path,'Edition/file/hash must identify one indexed retained source; missing or conflicting metadata is unresolved');continue
   if not exact[0].get('authority') or not exact[0].get('provenance'):error(path,'Indexed authoritative source provenance required');continue
   try:
    if not e['file'].startswith('data/requirements/'):raise ValueError('Source must be in authoritative-source area')
    actual=hashlib.sha256(schema.project.path(e['file']).read_bytes()).hexdigest()
    if actual!=e['sha256']:raise ValueError('Source bytes do not match selected edition hash')
    hashes[e['file']]=actual
   except (ValueError,OSError) as ex:error(path,str(ex));continue
   if e['file']==principal:primary_pinned=True
 if not primary_pinned:error('$.source_editions','The represented requirement primary source must be explicitly pinned')
 return dict(status='CALLER_DECLARED_ADMISSION_VALIDATED' if not errors else 'UNRESOLVED_ADMISSION',valid=not errors,errors=errors,input_hashes=hashes,context=None if errors else dict(declaration=copy.deepcopy(value),declaration_sha256=checksum(value),scope_definition_sha256=definition_hash(value),policy=POLICY,verification='Approved common experimental scope, declared class and retained source hashes checked. No input nodes, case identifiers, labels or counterparts loaded; no real-vessel eligibility or legal edition applicability certified.'))
def load_admission(project,config,schema,rid):
 path=config.get('admission_file')
 if not path:return dict(status='UNRESOLVED_ADMISSION',valid=False,errors=[dict(path='admission_file',message='Caller admission declaration required before either workflow may generate')],input_hashes={})
 try:
  from .core import GenerationProject
  file=GenerationProject(project.root).path(path);raw=file.read_bytes();obj=json.loads(raw)
 except (ValueError,OSError,TypeError) as ex:return dict(status='UNRESOLVED_ADMISSION',valid=False,errors=[dict(path='admission_file',message=str(ex))],input_hashes={})
 result=validate_declaration(obj,schema,rid);result['input_hashes'][path]=hashlib.sha256(raw).hexdigest();result['file']=path;return result

def target_findings(candidate,admission):
 """A class target is safe only under the mandatory complete-population data guard."""
 if not admission:return []
 try:g=Graph().parse(data=candidate.code,format='turtle')
 except Exception:return []
 f=admission['declaration']['focus_set'];owner=URIRef(f['owner_class']);classes=set(g.objects(None,SH.targetClass));nodes=set(map(str,g.objects(None,SH.targetNode)));implicit={s for s in g.subjects(RDF.type,SH.NodeShape) if (s,RDF.type,RDFS.Class) in g};bad=[]
 if classes-{owner}:bad.append('Other target classes select beyond declared population')
 if implicit-{owner}:bad.append('Implicit class targets select beyond declared population')
 if nodes:bad.append('Input-specific targetNode is outside the generic research-scope interface; use the declared record class and the independent per-input boundary')
 if any(g.objects(None,SH.targetSubjectsOf)) or any(g.objects(None,SH.targetObjectsOf)) or any(g.objects(None,SH.target)):bad.append('Unbounded/custom target route not supported by this admission boundary')
 if not classes and not implicit:bad.append('No target covering the declared admitted population')
 if bad:return [finding(candidate,'ADMISSION_SCOPE_ERROR','; '.join(bad),'',expected='Use the declared owner_class under the mandatory evaluation-only complete-population guard; do not request fixture identities or invent eligibility selectors',evidence=json.dumps(admission),suggestion='Constrain activation to the supplied population boundary. Preserve all represented conditions/query obligations and do not independently infer eligibility.',location='caller admission target boundary',contract_id='shared-admission',obligation_id='focus-boundary',check_id='target-boundary')]
 return []

def validate_data_scope(data,ontology,admission,binding=None,input_sha256=None):
 """Evaluation-only identity guard. No file access, outcome oracle, or model requests."""
 from owlrl import DeductiveClosure,RDFS_Semantics
 def unresolved(reason):return dict(valid=False,status='UNRESOLVED_ADMISSION',reason=reason)
 if not admission or 'declaration' not in admission:return unresolved('Explicit approved common scope required')
 declaration=admission['declaration']
 if declaration.get('approval',{}).get('status')!='APPROVED':return unresolved('Common scope is not approved')
 keys={'format_version','scope_id','scope_definition_sha256','input_sha256','admitted_nodes','construction_provenance'}
 if not isinstance(binding,dict) or set(binding)!=keys:return unresolved('Separate evaluation-only per-input binding required; it must never enter generation/review/repair')
 if binding['format_version']!=1 or binding['scope_id']!=declaration['admission_id'] or binding['scope_definition_sha256']!=definition_hash(declaration):return unresolved('Input binding refers to a different common scope')
 if not input_sha256 or binding['input_sha256']!=input_sha256 or not re.fullmatch('[0-9a-f]{64}',input_sha256):return unresolved('Input byte hash absent or does not match the reviewed binding')
 nodes=binding['admitted_nodes'];evidence=binding['construction_provenance']
 if not isinstance(nodes,list) or not nodes or any(not iri(n) for n in nodes) or len(nodes)!=len(set(nodes)):return unresolved('Nonempty unique absolute input identities required outside model context')
 if not isinstance(evidence,dict) or set(evidence)!={'kind','references'} or evidence['kind']!='SYNTHETIC_CONSTRUCTION_REVIEWED' or not isinstance(evidence['references'],list) or not evidence['references'] or any(not text(x) for x in evidence['references']):return unresolved('Reviewed synthetic construction provenance required, independently of labels/performance')
 f=declaration['focus_set'];graph=Graph()
 for t in ontology:graph.add(t)
 for t in data:graph.add(t)
 DeductiveClosure(RDFS_Semantics).expand(graph)
 actual={str(n) for n in graph.subjects(RDF.type,URIRef(f['owner_class']))};expected=set(nodes);valid=actual==expected and bool(expected)
 return dict(valid=valid,status='ADMITTED_DATA_BOUNDARY_MATCH' if valid else 'UNRESOLVED_ADMISSION',declared_nodes=sorted(expected),selected_nodes_with_rdfs=sorted(actual),missing_nodes=sorted(expected-actual),unadmitted_nodes=sorted(actual-expected),eligibility_independently_certified=False,reason='Evaluation-only population identity under an approved experimental assumption, not real-vessel eligibility certification')

def blocked_result(config,rid,result):
 return dict(version='0.9.1',method=config['method'],requirement_id=rid,status='UNRESOLVED_ADMISSION',admission_validation=result,candidate_attempts=0,provider_calls=0,generation_calls=0,repair_calls=0,auxiliary_format_retries=0,accepted_version=None,evaluation_candidate=None,history=[],complete_verification=False)
