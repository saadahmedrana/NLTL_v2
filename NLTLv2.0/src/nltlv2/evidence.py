"""Content-addressed supplied evidence; no ontology reads/inference or evaluation access."""
import copy,json,threading
from contextlib import contextmanager
import rdflib
from rdflib import Graph,BNode,Literal,XSD
from .core import digest
_LOCK=threading.RLock()
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
@contextmanager
def literal_identity():
 # rdflib defaults to lexical normalization. Identity checks must preserve lexical forms.
 with _LOCK:
  before=rdflib.NORMALIZE_LITERALS;rdflib.NORMALIZE_LITERALS=False
  try:yield
  finally:rdflib.NORMALIZE_LITERALS=before
def ground_fact(text):
 with literal_identity():g=Graph().parse(data=text,format='turtle')
 if len(g)!=1:raise ValueError('Exactly one explicit ground RDF triple required')
 triple=next(iter(g))
 if any(isinstance(t,BNode) for t in triple):raise ValueError('Blank-node facts have no supported stable ground-term identity')
 # RDF 1.1 plain strings are xsd:string; lexical numeric forms remain untouched.
 return tuple(Literal(str(t),datatype=XSD.string,normalize=False) if isinstance(t,Literal) and t.datatype is None and t.language is None else t for t in triple)
def fact_text(triple):return ' '.join(t.n3() for t in triple)+' .'
def evidence_catalog(context,execution=None):
 entries={}
 def add(kind,text,origin,terms=None):
  identity=dict(kind=kind,text=text,origin=origin);key='ev:'+digest(canonical(identity));entry=dict(evidence_id=key,kind=kind,text=text,text_sha256=digest(text),origin=origin)
  if terms is not None:entry['rdf_terms']=[t.n3() for t in terms]
  entries[key]=entry
 for doc in context.get('source_documents',[]):
  add('SOURCE',doc['text'],{k:copy.deepcopy(doc[k]) for k in ['file','sha256','edition','authority','selection'] if k in doc})
 for name in ['schema_terms','contract','quantityEncoding','retrieved_schema_evidence','admission','unresolvedOwnership','unresolvedSourceContext','retrieval_evidence','retrieval_gaps']:
  value=context.get(name)
  if value is None:continue
  if name in ['retrieved_schema_evidence','retrieval_evidence']:
   known={tuple(t) for t in context.get('ontology_evidence',[]) if isinstance(t,list) and len(t)==3}
   def without_duplicates(row):
    result=copy.deepcopy(row)
    if 'ontology_triples' in result:
     remaining=[t for t in result['ontology_triples'] if not isinstance(t,list) or tuple(t) not in known]
     if remaining:result['ontology_triples']=remaining
     else:result.pop('ontology_triples')
    return result
   value=[without_duplicates(row) for row in value]
  rows=value if name=='schema_terms' else [value]
  for row in rows:add('CALLER_DECLARATION' if name=='admission' else 'CONTEXT_STATUS' if name in ['unresolvedOwnership','unresolvedSourceContext','retrieval_evidence','retrieval_gaps'] else 'SCHEMA_TEXT',json.dumps(row,ensure_ascii=False,sort_keys=True),dict(context_field=name))
 # Only explicit triples already in the supplied context, never schema.graph lookup.
 for supplied in context.get('ontology_evidence',[]):
  if not isinstance(supplied,list) or len(supplied)!=3:continue
  try:triple=ground_fact(' '.join(supplied)+' .')
  except Exception:
   add('SCHEMA_TEXT',json.dumps(supplied,ensure_ascii=False),dict(context_field='ontology_evidence',limit='Text-only supplied fact; ground-term identity/equivalence unavailable. No inference or blank-node equivalence.'));continue
  add('RDF_FACT',fact_text(triple),dict(context_field='ontology_evidence',meaning='Explicit supplied triple only; no inferred ownership or regulatory implication'),triple)
 # Execution observations are supplied once in execution_probe, never as law/catalog facts.
 values=sorted(entries.values(),key=lambda e:e['evidence_id'])
 for i,entry in enumerate(values,1):
  entry['evidence_sha256']=entry['evidence_id'][3:];entry['provenance_sha256']=digest(canonical(entry['origin']));entry['evidence_id']='E'+str(i)
 return dict(format_version=2,entries=values,catalog_sha256=digest(canonical(values)),limits='Ground RDF triples only; exact RDF terms, no inference, no blank-node equivalence, no numeric value coercion. Source quotations remain verbatim.')
def citation_error(catalog,evidence_id,excerpt,*,source=False):
 entry=next((x for x in catalog['entries'] if x['evidence_id']==evidence_id),None)
 if entry is None:return 'MISSING_OR_UNSUPPLIED_EVIDENCE_ID','Use an evidence_id from this exact review packet'
 if source and entry['kind']!='SOURCE':return 'SOURCE_ID_KIND_MISMATCH','source_evidence_id must identify a SOURCE entry'
 if not isinstance(excerpt,str) or not excerpt.strip():return 'EMPTY_EVIDENCE_QUOTATION','Nonempty verbatim source/text quotation or equivalent single RDF_FACT serialization'
 if source or entry['kind']!='RDF_FACT':
  if excerpt not in entry['text']:return 'INVALID_SOURCE_QUOTATION' if source else 'UNSUPPORTED_SCHEMA_EVIDENCE','Copy an exact substring of the referenced entry text, retaining whitespace'
 else:
  try:parsed=ground_fact(excerpt);expected=ground_fact(entry['text'])
  except Exception:return 'INVALID_RDF_FACT_QUOTATION','One ground Turtle/N-Triples fact; no blank nodes, imports or inference'
  if parsed!=expected:return 'ALTERED_OR_UNSUPPORTED_RDF_FACT','Exact subject/predicate/object RDF terms of the referenced supplied fact; datatype, lexical form and language preserved'
 return None
CITATION_FORMAT=dict(source='source_evidence_id + source_excerpt: verbatim nonempty substring of that SOURCE text; preserve whitespace',schema='evidence_id + evidence_excerpt: exact substring of referenced text. RDF_FACT permits a single equivalent Turtle/N-Triples fact with exact RDF terms only.',code='candidate_location / previous_location: {candidate_version, candidate_sha256, unit: lines|characters, start, end}; lines are inclusive one-based, Unicode character offsets half-open zero-based. Exact code is extracted server-side; do not reproduce indentation.',state='Echo candidate_version, candidate_sha256 and review_request_id. Reconcile only IDs in original prior_issues. Failed review output is not state.',limits='Do not cite arbitrary ontology facts, unsupplied context, inference or numeric-value equivalence as RDF identity.')
def probe_summary(c,probe=None,reason='No execution probe was run for this candidate'):
 if probe is None:return dict(candidate_version=c.version,candidate_sha256=c.sha256,engine_outcome='NOT_RUN',exact_diagnostics=dict(reason=reason),regulatory_correctness_established=False)
 if probe.get('candidate_sha256') not in [None,c.sha256] or probe.get('candidate_version') not in [None,c.version]:raise ValueError('STALE_EXECUTION_PROBE_INTEGRITY_FAILURE')
 return dict(candidate_version=c.version,candidate_sha256=c.sha256,engine='pyshacl',engine_version=probe.get('engine_version','NOT_EMBEDDED_IN_LEGACY_ARTIFACT'),engine_outcome=probe.get('engine_outcome','HISTORICAL_ERROR_RECORDED' if probe.get('error') else 'HISTORICAL_COMPLETED_PROBE_ARTIFACT'),exact_diagnostics={k:probe[k] for k in ['error','failure_kind','stdout','stderr'] if k in probe},diagnostic_availability='Captured verbatim' if 'stdout' in probe else 'Legacy artifact did not capture successful engine stdout/stderr',activation=probe.get('activation'),regulatory_correctness_established=False,scope='Execution-only schema-derived probe; no expected regulatory verdict; success is not complete correctness')
def review_binding(c,context,prior=(),previous=None,changes=None,execution=None,*,questions=()):
 catalog=evidence_catalog(context,execution);identity=dict(candidate_version=c.version,candidate_sha256=c.sha256,context_sha256=digest(canonical(context)),catalog_sha256=catalog['catalog_sha256'],prior_issues=list(prior),previous_candidate=None if previous is None else dict(version=previous.version,sha256=previous.sha256,full_code=previous.code),changes=(changes or {}).get('changes',[]),execution_probe=execution)
 if questions:identity['prior_context_questions']=list(questions)
 return dict(candidate_version=c.version,candidate_sha256=c.sha256,review_request_id='review:'+digest(canonical(identity)))
def assert_review_packet(body,c):
 if body.get('protocol_version')==2 and 'packet_sha256' in body:
  from .requests import assert_compact_review
  return assert_compact_review(body,c)
 from .core import Candidate
 previous=body.get('previous_candidate');p=None if previous is None else Candidate(previous['version'],previous['full_code'],'')
 expected=review_binding(c,body['context'],body['prior_issues'],p,body['change_manifest'],body.get('execution_probe'),questions=body.get('prior_context_questions',()))
 if type(body.get('candidate_version')) is not int or any(body.get(k)!=v for k,v in expected.items()) or body['full_candidate']!=c.code:raise ValueError('STALE_REVIEW_STATE_INTEGRITY_FAILURE')
 if body.get('evidence_catalog')!=evidence_catalog(body['context'],body.get('execution_probe')):raise ValueError('UNSUPPLIED_REVIEW_EVIDENCE_INTEGRITY_FAILURE')
 execution=body.get('execution_probe')
 if not execution or execution.get('candidate_sha256')!=c.sha256 or execution.get('candidate_version')!=c.version:raise ValueError('STALE_OR_ABSENT_EXECUTION_SUMMARY_INTEGRITY_FAILURE')
 return expected


def code_location(candidate,start,end,*,unit='characters'):
 """Half-open Unicode character offsets or inclusive one-based whole line ranges."""
 return dict(candidate_version=candidate.version,candidate_sha256=candidate.sha256,unit=unit,start=start,end=end)

def extract_location(location,candidate):
 if not isinstance(location,dict) or set(location)!={'candidate_version','candidate_sha256','unit','start','end'}:raise ValueError('INVALID_CODE_LOCATION')
 if type(location['candidate_version']) is not int or location['candidate_version']!=candidate.version or location['candidate_sha256']!=candidate.sha256:raise ValueError('STALE_CODE_LOCATION')
 a,b=location['start'],location['end']
 if type(a) is not int or type(b) is not int:raise ValueError('INVALID_CODE_RANGE')
 if location['unit']=='lines':
  lines=candidate.code.splitlines(keepends=True)
  if not 1<=a<=b<=len(lines):raise ValueError('INVALID_CODE_RANGE')
  return ''.join(lines[a-1:b])
 if location['unit']!='characters' or not 0<=a<b<=len(candidate.code):raise ValueError('INVALID_CODE_RANGE')
 return candidate.code[a:b]

def resolve_locations(obj,candidate,previous=None,*,required=False):
 """Extract code on the server. Never repair an asserted, altered quotation."""
 errors=[]
 def walk(x,path='$'):
  if isinstance(x,list):
   for i,v in enumerate(x):walk(v,path+'['+str(i)+']')
  elif isinstance(x,dict):
   from .review_protocol import context_only
   grounded=('source_excerpt' in x or 'source_evidence_id' in x or 'evidence_id' in x) and (not context_only(x) or 'change_id' in x and 'disposition' in x)
   for field,target,code in [('candidate_location',candidate,'candidate_excerpt'),('previous_location',previous,'previous_excerpt')]:
    if field not in x:
     if required and grounded and (field=='candidate_location' or 'change_id' in x and 'disposition' in x and field=='previous_location'):
      errors.append(dict(code='MISSING_CODE_LOCATION',path=path+'.'+field,expected='Candidate-bound range; code quotations are extracted server-side',observed=None,category='INVALID_CANDIDATE_QUOTATION'))
     continue
    if x[field] is None and context_only(x):continue
    try:
     if target is None:raise ValueError('ABSENT_PREVIOUS_CANDIDATE')
     exact=extract_location(x[field],target)
     if x.get(code) and x[code]!=exact:raise ValueError('ASSERTED_CODE_QUOTATION_MISMATCH')
     x[code]=exact
    except ValueError as e:errors.append(dict(code=str(e),path=path+'.'+field,expected='Valid range bound to exact candidate/version/hash',observed=x[field],category='INVALID_CANDIDATE_QUOTATION'))
   for k,v in list(x.items()):
    if k not in ['candidate_location','previous_location']:walk(v,path+'.'+k)
 walk(obj)
 return errors


def wire_catalog(catalog):
 """Public aliases and evidence once; immutable hash/provenance map stays in artifacts."""
 entries=[]
 for entry in catalog['entries']:
  origin=entry['origin']
  if entry['kind']=='SOURCE':
   provenance={k:origin[k] for k in ['file','edition','authority'] if k in origin}
   if origin.get('selection'):provenance['selection']={k:v for k,v in origin['selection'].items() if k in ['start','end','line_start','line_end','page_start','page_end']}
  else:provenance={k:origin[k] for k in ['context_field','limit'] if k in origin}
  public=dict(evidence_id=entry['evidence_id'],kind=entry['kind'],text=entry['text'])
  if provenance:public['origin']=provenance
  entries.append(public)
 return dict(format_version=2,catalog_sha256=catalog['catalog_sha256'],entries=entries,limits=catalog['limits'])
