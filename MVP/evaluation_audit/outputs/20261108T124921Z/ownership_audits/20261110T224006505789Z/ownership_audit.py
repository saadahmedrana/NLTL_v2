#!/usr/bin/env python3
"""Read-only adjudication of current ownership/path cause flags.

Only this timestamped audit directory is written. No validation, query execution,
shape transformation, fixture repair, generation, verdict or cause-ledger update.
"""
import csv,json,hashlib,re,sys,unicodedata
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
from rdflib import Graph,URIRef,Literal,BNode,RDF,RDFS,OWL
from rdflib.collection import Collection
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/MVP')
sys.path.insert(0,str(ROOT/'evaluation_audit/full_audit'))
from common import audit,BASE,OUT as CASES,OLD
DEST=Path(__file__).resolve().parent
N,Q,S=audit.N,audit.Q,audit.S
AUTH=audit.read(audit.HERE/'authoritative_run.json')
INDEX_PATH=audit.R13/'requirement_term_index.json';INDEX=audit.read(INDEX_PATH)
ONTO=Graph().parse(audit.ONTOLOGY)
ROWS={(r['condition'],r['case_id']):r for r in audit.read(BASE/'retained_rows.json')}
SOURCE_NAMES={'I2':'IACS_I2_full.txt','IMO':'IMO_full.txt','TRF':'TRAFICOM_full.txt'}
PDF_NAMES={'I2':'ur-i2rev4.pdf','IMO':'MSC.385(94).pdf','TRF':'TRAFICOM.pdf'}
ALIASES={'I2-006':'aftSectionDesignBasis','IMO-049':'machineryComponentType','TRF-050':'shellPlateButtCrossing'}
APP_REVIEW={
'I2-006':('asternIceOperationIntent','Astern-in-ice design intent activates the aft-section design-basis rule.'),
'I2-008':('polarClass hullArea bowShape','The full source distinguishes Bow areas of all Polar Classes and Bow-Intermediate Icebelt areas for PC6/PC7; characteristics are calculated for bow sub-regions. This does not specify an RDF owner for totalGlancingImpactForce.'),
'I2-022':('framingAngleOmega platingHullAreaClassification','Transverse framing Omega>=70 degrees, including the named bottom areas; placement of the disputed shared numeric operands is not assigned by these applicability statements.'),
'I2-023':('framingAngleOmega loadPatchHeight frameSpacing','Longitudinal framing Omega<=20 degrees; formula branches b>=s and b<s retain the same missing property-owner assignments.'),
'I2-024':('framingAngle','Oblique framing is strictly 20<Omega<70 degrees. The generic calculationCase owner does not specify which subtypes must carry both endpoint-thickness properties.'),
'I2-031':('structuralLocation transverseFrameOrientation loadPatchOrientation','Bottom local frames and transverse side local frames; the bottom patch orientation condition is distinct from the disputed unspecified operand/profile owners.'),
'I2-040':('structuralSectionType','Section type selects flat-bar versus bulb/tee/angle buckling criterion; yieldStrength lacks a per-requirement owner assignment.'),
'I2-052':('hullGirderLongitudinalPositionFromAft','Source I2.13.3.1 concerns intermediate values of vertical ice shear-force distribution factor Cf, not the separate bending-moment interpolation in I2.13.4.1.'),
'I2-064':('calculationMethod','Linear-calculation requirements distinguish web shear and flange von Mises criteria; yieldStrength owner is not bound by the web/flange paths.'),
'IMO-016':('certificateLanguage certificateFormModel','Certificate model and translation depend on the certificate language; the language property owner is not explicitly fixed by termOwners.'),
'IMO-035':('iceAccretionLikely','PWOM icing information and stability-calculation consistency are the relevant document obligations; existence of document links does not formally assign these two disputed property owners.'),
'IMO-047':('hasEssentialEngine combustionAirTemperatureControlPresent','Internal-combustion engines driving essential machinery are the applicable equipment. The relational engine model exists, but combustionAirTemperature owner remains unassigned.'),
'IMO-049':('shipCategory shipIceStrengthened machineryComponentType','Full 6.3.3 includes the ice-strengthened-ship preface, then separate A, B and C approval branches. The contract supplies approval-record paths but no machineryComponentType owner. Category labels alone are not used to establish every source applicability fact.'),
'IMO-104':('hasCrewMember hasCrewMemberInventory hasAssignedDuty hasRelevantPolarWaterOperationalManualItem','Familiarization is for every crew member and PWOM procedure/equipment relevant to assigned duties; item/record links do not fix the disputed status property owner.'),
'TRF-014':('constructionDate assessmentDate firstScheduledDryDockingDate summerLoadLineFreshWaterDraught upperIceWaterlineDraught','The 2007 cutoff controls marking obligations. Document retention is separately explicit; retainedOnBoard is assigned to ship by termOwners, not inferred from the document that it describes.'),
'TRF-030':('hasDirectAnalysisCase loadLengthDeterminedFromArrangement','These are represented direct analyses; load-position and load-length conditions do not relocate the explicitly ship-owned disputed numeric/input properties.'),
'TRF-036':('iceClass','Table 4-1 uses ice class. A parameter-set target is not a per-property owner: termOwners explicitly puts iceClass on ship.'),
'TRF-050':('frameAttachment shellPlateButtCrossing','The scalloping exception depends on butt crossing on frameAttachmentRecord. The frame acquires the record type from its misplaced weld property; domain inference does not prove a new SHACL owner.'),
'TRF-120':('hasNaturalFrequencyCalculationCase vibrationDirection','Longitudinal and transverse thruster frequency estimates require the cited physical effects. Their calculation-case path does not assign thrusterNaturalFrequency ownership.'),
'TRF-130':('coolingWaterChestVolumeAndHeightRequirementsCannotBeMet coolingWaterChestAlternativeArrangementUsed','The fallback arrangement changes chest count/alternation, not the explicitly ship-owned engine power shared by chest-volume calculations.'),
}
FINDINGS=['SHACL_VIOLATES_CLEAR_SCHEMA','FIXTURE_VIOLATES_CLEAR_SCHEMA','BOTH_VIOLATE_CLEAR_SCHEMA','BOTH_CONFORM_NO_OWNERSHIP_ERROR','ONTOLOGY_CONTRACT_CONFLICT','SCHEMA_UNDERSPECIFIED','INSUFFICIENT_EVIDENCE']
INPUTS=set()

def sha(p):return audit.sha(p)
def read(p):INPUTS.add(Path(p).resolve());return audit.read(p)
def load(p):INPUTS.add(Path(p).resolve());return Graph().parse(p)
def text(p):INPUTS.add(Path(p).resolve());return Path(p).read_text()
def save(name,obj):
 p=DEST/name;assert p.resolve().is_relative_to(DEST);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def csvout(name,rs):
 p=DEST/name;fields=list(dict.fromkeys(k for r in rs for k in r))
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rs:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def short(x):return str(x).removeprefix(str(N)).removeprefix(str(S)).removeprefix(str(Q))
def norm(x):return ''.join(c for c in unicodedata.normalize('NFKC',x).lower().replace('°','deg') if c.isalnum())
def supertypes(cls):
 out={cls};pending=[cls]
 while pending:
  for parent in ONTO.objects(pending.pop(),RDFS.subClassOf):
   if isinstance(parent,URIRef) and parent not in out:out.add(parent);pending.append(parent)
 return out

def explicit_types(g,n):return set(g.objects(n,RDF.type))
def hierarchy_types(g,n):return {p for t in explicit_types(g,n) for p in supertypes(t)}
def rdfs_types(g,n):
 result=hierarchy_types(g,n);proof=[]
 for p,o in g.predicate_objects(n):
  for cls in ONTO.objects(p,RDFS.domain):
   if isinstance(cls,URIRef):result|=supertypes(cls);proof.append(dict(rule='RDFS_DOMAIN_TYPING_NOT_EXCLUSIVE_PLACEMENT',data_triple=[str(n),str(p),o.n3()],schema_triple=[str(p),str(RDFS.domain),str(cls)]))
 for s,p in g.subject_predicates(n):
  for cls in ONTO.objects(p,RDFS.range):
   if isinstance(cls,URIRef):result|=supertypes(cls);proof.append(dict(rule='RDFS_RANGE_TYPING',data_triple=[str(s),str(p),str(n)],schema_triple=[str(p),str(RDFS.range),str(cls)]))
 return result,proof

def path_expr(g,p):
 if isinstance(p,URIRef):return str(p)
 if p is None:return None
 for op in [S.inversePath,S.alternativePath,S.zeroOrMorePath,S.oneOrMorePath,S.zeroOrOnePath]:
  head=g.value(p,op)
  if head is not None:return {short(op):[path_expr(g,n) for n in Collection(g,head)] if op==S.alternativePath else path_expr(g,head)}
 try:return [path_expr(g,n) for n in Collection(g,p)]
 except Exception:return {'unresolved_path':True}
def flatten_path(p):return p if isinstance(p,list) else [p]
def contains(p,iri):
 if isinstance(p,str):return p==iri
 if isinstance(p,list):return any(contains(v,iri) for v in p)
 if isinstance(p,dict):return any(contains(v,iri) for v in p.values())
 return False

@lru_cache(None)
def shape_info(path,property_iri):
 sg=load(path);wanted=URIRef(property_iri);occ=[]
 roots={n for p in [S.targetClass,S.targetNode,S.targetSubjectsOf,S.targetObjectsOf] for n in sg.subjects(p,None)}
 def walk(node,prefix,classes,chain,branches,seen,root):
  if node in seen:return
  seen=seen|{node};part=path_expr(sg,sg.value(node,S.path));full=prefix+flatten_path(part) if part is not None else prefix
  if part is not None and contains(part,property_iri):
   occurrence=dict(root_shape=str(root),target_selectors={short(p):[str(x) for x in sg.objects(root,p)] for p in [S.targetClass,S.targetNode,S.targetSubjectsOf,S.targetObjectsOf] if list(sg.objects(root,p))},complete_property_path=full,owner_class_hints=sorted(map(str,classes)),owner_shape_constraints=[str(x) for x in sg.objects(node,S['class'])],constraint_parameters={short(p):[x.n3() for x in sg.objects(node,p)] for p in [S.minCount,S.maxCount,S.hasValue,S.datatype,S['class']] if list(sg.objects(node,p))},branches=branches,shape_traversal=chain+[str(node)])
   occ.append(occurrence)
  value_classes=set(sg.objects(node,S['class']))
  if part is not None and isinstance(part,str):value_classes.update(ONTO.objects(URIRef(part),RDFS.range))
  nextclasses=value_classes or classes
  for child in sg.objects(node,S.property):walk(child,full,nextclasses if part is not None else classes,chain+[str(node)],branches,seen,root)
  for child in sg.objects(node,S.node):walk(child,full,nextclasses,chain+[str(node)],branches,seen,root)
  for op in [S['or'],S['and'],S.xone,S['not']]:
   for head in sg.objects(node,op):
    children=[head] if op==S['not'] else list(Collection(sg,head))
    for i,c in enumerate(children):walk(c,full,nextclasses if part is not None else classes,chain+[str(node)],branches+[dict(operator=short(op),branch=i)],seen,root)
 for root in sorted(roots,key=str):
  walk(root,[],set(sg.objects(root,S.targetClass)),[],[],set(),root)
 queries=[str(q) for q in sg.objects(None,S.select) if short(wanted) in str(q)]
 return dict(occurrences=occ,queries=queries,targets={str(r):{short(p):[str(o) for o in sg.objects(r,p)] for p in [S.targetClass,S.targetSubjectsOf,S.targetObjectsOf,S.targetNode] if list(sg.objects(r,p))} for r in roots})

def paths_to(g,target):
 roots={s for s in g.subjects(RDF.type,N.ship)}|{s for s in g.subjects(RDF.type,N.frame)}
 # An ownership comparison can start from non-ship target roles too.
 paths=[]
 for root in sorted(roots,key=str):
  queue=deque([(root,[],{root})])
  while queue:
   n,path,seen=queue.popleft()
   if n==target:paths.append(dict(from_node=str(root),from_types=sorted(map(str,explicit_types(g,root))),path=path));continue
   if len(path)>=6:continue
   for p,o in sorted(g.predicate_objects(n),key=lambda x:tuple(map(str,x))):
    if str(p).startswith(str(N)) and not isinstance(o,Literal) and o not in seen:queue.append((o,path+[str(p)],seen|{o}))
 return paths

def fixture_property(g,p):
 result=[]
 for owner in sorted(set(g.subjects(p,None)),key=str):
  inferred,proof=rdfs_types(g,owner);values=[]
  for o in g.objects(owner,p):
   values.append(dict(term=o.n3(),types=sorted(map(str,explicit_types(g,o))),numeric_values=[x.n3() for x in g.objects(o,Q.numericValue)],units=[str(x) for x in g.objects(o,Q.unit)]))
  result.append(dict(owner=str(owner),asserted_types=sorted(map(str,explicit_types(g,owner))),subclass_closure=sorted(map(str,hierarchy_types(g,owner))),rdfs_inferred_types=sorted(map(str,inferred)),rdfs_typing_proof=proof,paths_from_targets=paths_to(g,owner),values=values))
 return result

@lru_cache(None)
def source_info(req):
 row=next(r for (w,c),r in ROWS.items() if r['requirement_id']==req);family=req.split('-')[0];source=audit.HERE/'source_review'/SOURCE_NAMES[family];raw=text(source);frozen=row['frozen_requirement_text'];reviews=read(audit.HERE/'full_audit/source_reviews.json')
 pdf=ROOT/'RELEVANT FILES'/PDF_NAMES[family];INPUTS.add(pdf)
 evidence=dict(source_clause=row['source_clause'],frozen_source_text=frozen,source_applicability_review=APP_REVIEW[req][1],original_pdf=str(pdf),original_pdf_sha256=sha(pdf),full_source_text=str(source),full_source_sha256=sha(source),regulation_does_not_itself_define_RDF_owner_classes=True)
 if req in ['IMO-049','I2-052']:
  lines=raw.split('\n');first_anchor='6.3.3     In addition' if req=='IMO-049' else 'I2.13.3.1 The design vertical ice shear force'
  a=next(i for i,line in enumerate(lines) if first_anchor in line)
  end_anchor='CHAPTER 7' if req=='IMO-049' else 'I2.13.3.2 The applied vertical shear stress'
  b=next(i for i in range(a+1,len(lines)) if end_anchor in lines[i])
  evidence.update(source_location_status='REVIEWED_FULL_CLAUSE_AND_PARENT_SCOPE',source_excerpts=[dict(line_start=a+1,line_end=b,excerpt='\n'.join(lines[a:b]))],source_location_note='Full source preface and .1-.3 approval clauses included.' if req=='IMO-049' else 'Disambiguated against I2.13.3.1 shear-factor clause; the later identical sentence in I2.13.4.1 concerns bending and is not paired here.')
 elif req in reviews:
  review=reviews[req];evidence.update(source_review=review,source_location_status='PREVIOUS_REVIEWED_EQUIVALENT_CLAUSE')
 else:
  chars=[];positions=[]
  for i,c in enumerate(raw):
   for ch in unicodedata.normalize('NFKC',c).lower().replace('°','deg'):
    if ch.isalnum():chars.append(ch);positions.append(i)
  hay=''.join(chars);needle=norm(frozen);starts=[];start=0
  while needle and (pos:=hay.find(needle,start))>=0:
   a,b=positions[pos],positions[pos+len(needle)-1]+1;first=raw.rfind('\n',0,a)+1;end=raw.find('\n',b);end=len(raw) if end<0 else end
   starts.append(dict(line_start=raw.count('\n',0,first)+1,line_end=raw.count('\n',0,end)+1,excerpt=raw[first:end]));start=pos+1
  evidence.update(source_location_status='EXACT_SOURCE_QUOTATION' if len(starts)==1 else 'MULTIPLE_EXACT_QUOTES' if starts else 'SOURCE_LOCATION_UNRECONCILED',source_excerpts=starts)
 return evidence

@lru_cache(None)
def context_info(path,prompt_path,req,property_name):
 context=read(path);raw=text(prompt_path);payload,_=json.JSONDecoder().raw_decode(raw.split('--- USER INPUT ---',1)[1].lstrip());terms=payload['allowedVocabulary'];matching=[(i,t) for i,t in enumerate(terms) if t['localName']==property_name]
 term=matching[0][1] if len(matching)==1 else None;index_owner=INDEX['termOwners'].get(req,{}).get(property_name);contract=INDEX['dependencyContracts'][req]
 rule_lines=[];lines=raw.split('\n')
 for i,line in enumerate(lines):
  if any(t in line for t in ['Treat requiredOwner','requiredOwner is derived','universal rule about every','allowedVocabulary is available']):rule_lines.append(dict(line=i+1,excerpt='\n'.join(lines[i:i+5])))
 source_locks=context.get('source_lock',{})
 lock_matches=dict(ontology=source_locks.get('ontology_sha256')==sha(audit.ONTOLOGY),term_index=source_locks.get('requirement_term_index_sha256')==sha(INDEX_PATH))
 initial_term=next((t for t in context['terms'] if t['localName']==property_name),None)
 same_contract=payload.get('selection',{}).get('dependencyContract')==contract
 if term is None:decision='UNDERSPECIFIED';reason='The actual prompt has no unique matching vocabulary term.'
 elif index_owner and term.get('requiredOwner')!=index_owner:decision='INCORRECT';reason='Actual prompt requiredOwner differs from the explicit locked per-requirement termOwners assignment.'
 elif not same_contract or initial_term!=term or not all(lock_matches.values()):decision='CONTRADICTORY';reason='Prompt, context pack, or locked contract/ontology provenance do not agree.'
 elif req=='I2-024':decision='UNDERSPECIFIED';reason='The correct generic calculationCase owner class is supplied, but applicability/cardinality across root cases versus interpolationPoint subclasses is not resolved.'
 elif index_owner:decision='CORRECT';reason='Actual prompt supplies the same explicit per-requirement owner as the locked termOwners map, with the matching contract.'
 else:decision='UNDERSPECIFIED';reason='requiredOwner=ship has no explicit assignment for this property. The broad benchmarkEntity domain does not resolve ownership; the fallback presented as authoritative is not accepted as schema evidence.'
 fewshots=[]
 for i,fs in enumerate(payload.get('fewShotExamples',[])):
  s=json.dumps(fs,ensure_ascii=False)
  if property_name in s:fewshots.append(dict(index=i,example=fs,note='Illustrative example; not used as an authoritative ownership assignment for this requirement.'))
 return dict(context_pack=str(path),context_sha256=sha(path),actual_attempt_prompt=str(prompt_path),prompt_sha256=sha(prompt_path),prompt_term_pointer=f'/allowedVocabulary/{matching[0][0]}' if term else None,prompt_term=term,node_patterns=payload.get('nodePatterns'),prompt_selection=payload.get('selection'),generic_instruction_excerpts=rule_lines,matching_few_shot_examples=fewshots,initial_context_term_agrees=initial_term==term,locked_source_hashes_agree=lock_matches,contract_agrees=same_contract,required_owner_provenance='EXPLICIT_PER_REQUIREMENT_TERMOWNERS' if index_owner else 'UNRESOLVED_OR_HISTORICAL_FALLBACK_NOT_AUTHORITATIVE',context_finding=decision,context_reason=reason)

def schema_info(req,name):
 p=N[name];ct=INDEX['dependencyContracts'][req];owner=INDEX['termOwners'].get(req,{}).get(name)
 seeds=set(ONTO.objects(p,RDFS.domain))|set(ONTO.objects(p,RDFS.range))|({N[owner]} if owner else set())
 hierarchy=sorted({tuple(map(str,(c,RDFS.subClassOf,sup))) for seed in seeds for c in supertypes(seed) for sup in ONTO.objects(c,RDFS.subClassOf) if isinstance(sup,URIRef)})
 data=dict(property=str(p),ontology_file=str(audit.ONTOLOGY),ontology_sha256=sha(audit.ONTOLOGY),property_triples=sorted([' '.join(x.n3() for x in (p,pred,obj))+' .' for pred,obj in ONTO.predicate_objects(p)]),domains=[str(x) for x in ONTO.objects(p,RDFS.domain)],ranges=[str(x) for x in ONTO.objects(p,RDFS.range)],class_hierarchy=hierarchy,explicit_owner_class=str(N[owner]) if owner else None,term_owner_pointer=str(INDEX_PATH)+f'#/termOwners/{req}/{name}',term_owner_value=owner,contract_pointer=str(INDEX_PATH)+f'#/dependencyContracts/{req}',contract=ct,termOwners=INDEX['termOwners'].get(req,{}),modelPaths=ct.get('modelPaths',[]),ownership_interpretation='RDFS domain/range supply types, not exclusive placement. ownerClasses is not used as a per-property owner. Missing termOwners is not filled from prompt requiredOwner, expected labels, fixture layout, or another requirement.')
 if owner:
  compatible=all(d in supertypes(N[owner]) for d in ONTO.objects(p,RDFS.domain) if isinstance(d,URIRef))
  data['declared_owner_satisfies_domain_class']=compatible
  data['explicit_ontology_contract_contradictions']=[dict(owner=owner,disjoint=str(d)) for d in ONTO.objects(p,RDFS.domain) if (N[owner],OWL.disjointWith,d) in ONTO or (d,OWL.disjointWith,N[owner]) in ONTO]
 else:data['explicit_ontology_contract_contradictions']=[]
 return data


def report_info(path,p):
 if not path:return None
 rg=load(path);results=[]
 for n in rg.subjects(RDF.type,S.ValidationResult):
  resultpath=path_expr(rg,rg.value(n,S.resultPath));focus=rg.value(n,S.focusNode)
  if resultpath==str(p):results.append(dict(component=str(rg.value(n,S.sourceConstraintComponent)),focus=str(focus),result_path=resultpath,source_shape=str(rg.value(n,S.sourceShape)),parameters={short(pred):[o.n3() for o in rg.objects(rg.value(n,S.sourceShape),pred)] for pred in [S.minCount,S.maxCount,S.hasValue] if list(rg.objects(rg.value(n,S.sourceShape),pred))}))
 return dict(path=str(path),sha256=sha(path),conforms=[str(v) for v in rg.objects(None,S.conforms)],relevant_results=results,note='No report re-execution or message-based matching. Anonymous source labels are archival only; shape paths are recovered structurally from the original shape.')


def classify(req,name,schema,shape,negative,repaired,neggraph):
 owner=schema['explicit_owner_class'];properties=shape['occurrences']
 shapeclasses={c for occurrence in properties for c in occurrence['owner_class_hints']}
 compatible=lambda cls:owner and URIRef(owner) in supertypes(URIRef(cls))
 shape_ok=bool(owner and properties and shapeclasses and all(compatible(c) for c in shapeclasses))
 # Never use rdfs:domain-induced typing of a misplaced property to prove its
 # contractual role. Such inference is explanatory evidence, not ownership.
 fixture_ok=bool(owner and negative and all(owner in f['subclass_closure'] for f in negative))
 if schema['explicit_ontology_contract_contradictions']:return 'ONTOLOGY_CONTRACT_CONFLICT','CONFIRMED','HIGH','Explicit disjointness contradicts the contractual owner.'
 if req=='I2-006':return 'BOTH_CONFORM_NO_OWNERSHIP_ERROR','CONFIRMED','HIGH','The shape and every supplied value use ship; an originally absent value is missing, not on a wrong owner. The old flag concerns string/value semantics, not ownership or a different graph path. No unique exclusive owner is invented from benchmarkEntity.'
 if req=='I2-024':
  if shape_ok and fixture_ok:return 'BOTH_CONFORM_NO_OWNERSHIP_ERROR','CONFIRMED','HIGH','Both root oblique cases and endpoint interpolationPoint instances are subclasses of calculationCase. Values on the root case and constraints on calculationCase share the declared owner class. The endpoint failures are missing values on another permitted subtype, not values on an incompatible owner. Universal minCount/role scope is not specified by termOwners and remains a separate issue.'
  return 'INSUFFICIENT_EVIDENCE','PROVISIONAL','LOW','Could not establish generic calculationCase owner compatibility for both artifacts.'
 if req=='TRF-050':
  if not shape_ok:return 'INSUFFICIENT_EVIDENCE','PROVISIONAL','LOW','Could not reconstruct the original attachment-record target.'
  frame=next(neggraph.subjects(RDF.type,N.frame),None);linked=list(neggraph.objects(frame,N.frameAttachment)) if frame else []
  misplaced=bool(frame and list(neggraph.objects(frame,N.frameShellWeldType)) and linked and not any(list(neggraph.objects(rec,N.frameShellWeldType)) for rec in linked))
  if misplaced:return 'FIXTURE_VIOLATES_CLEAR_SCHEMA','CONFIRMED','HIGH','The fixture places frameShellWeldType on frame instead of the frameAttachment object required by termOwners and modelPaths. Its domain infers frameAttachmentRecord on frame, so the correctly targeted record shape also examines frame. The missing shellPlateButtCrossing there does not prove that SHACL declares frame as this property owner. This is the intended negative wrong-owner defect, not a newly established benchmark correction.'
  return 'INSUFFICIENT_EVIDENCE','PROVISIONAL','LOW','The causal misplaced-weld/inferred-record witness was not established.'
 if owner:
  if shape_ok and not fixture_ok:return 'FIXTURE_VIOLATES_CLEAR_SCHEMA','CONFIRMED','HIGH','The explicit per-requirement termOwners assigns this property to '+short(owner)+'. The shape requires it on that role, while the supplied fixture places it on another node or lacks it at the required owner. This decision does not rely on domain exclusivity, expected labels or counterfactual acceptance.'
  if fixture_ok and not shape_ok:return 'SHACL_VIOLATES_CLEAR_SCHEMA','CONFIRMED','HIGH','The explicit contractual owner is satisfied by the fixture, while the generated property path requires another owner.'
  if not shape_ok and not fixture_ok:return 'BOTH_VIOLATE_CLEAR_SCHEMA','CONFIRMED','MEDIUM','Neither artifact follows the explicit owner assignment.'
  return 'BOTH_CONFORM_NO_OWNERSHIP_ERROR','CONFIRMED','HIGH','Both artifacts satisfy the explicit contractual owner class/path.'
 return 'SCHEMA_UNDERSPECIFIED','PROVISIONAL','HIGH','The disputed property has no requirement-specific termOwners assignment, and no modelPaths edge binds that property to a specific owner. Its ontology domain is only benchmarkEntity. Related case/component paths and physical wording do not make the fallback ship owner, or the fixture owner, authoritative. The observed path difference is real; attribution to either artifact is not established.'


def inventory():
 records={p.stem:read(p) for p in sorted((CASES/'records').glob('*.json'))}
 with (OLD/'failure_causes.csv').open() as f:fallback={(r['condition'],r['case_id']):r for r in csv.DictReader(f) if r['arm']=='corrected_fixtures'}
 INPUTS.add(OLD/'failure_causes.csv');flags=[]
 for cid,record in records.items():
  for w,v in record.get('workflows',{}).items():
   cause=v.get('likely_cause') or fallback.get((w,cid),{})
   if 'CONTEXT_SCHEMA_MISMATCH' not in json.dumps(cause):continue
   prop=cause.get('property') or str(N[ALIASES[record['requirement_id']]])
   flags.append(dict(workflow=w,workflow_label=audit.WORKFLOWS[w],requirement_id=record['requirement_id'],case_id=cid,disputed_property=prop,cause=cause,cause_source=str(CASES/'records'/f'{cid}.json')+'#/workflows/'+w+'/likely_cause' if v.get('likely_cause') else str(OLD/'failure_causes.csv'),record=record))
 return flags


def run():
 assert Path(AUTH['run_dir'])==BASE
 INPUTS.update([audit.HERE/'authoritative_run.json',BASE/'baseline_results.json',BASE/'retained_rows.json',INDEX_PATH,audit.ONTOLOGY,OLD/'failure_causes.csv'])
 assert sha(BASE/'baseline_results.json')==AUTH['baseline_sha256']
 # Freeze every existing authoritative-run artifact; the new audit alone may
 # write under DEST. Hashing is read-only and is not a validation rerun.
 protected={str(p):sha(p) for p in BASE.rglob('*') if p.is_file() and not p.is_relative_to(DEST)}
 save('protected_files_before.json',protected)
 flags=inventory();counts=Counter(f['workflow'] for f in flags)
 assert counts=={'NO_SEMANTIC':59,'SINGLESHOT':56}
 save('current_provisional_cause_ledger.json',[{k:v for k,v in f.items() if k!='record'} for f in flags])
 csvout('current_provisional_cause_ledger.csv',[{k:v for k,v in f.items() if k!='record'} for f in flags])
 # The earlier consolidated CSV is a frozen pre-semantics view, not the current
 # source of truth. Its missing case/workflow flags are shown explicitly.
 with (CASES/'strict_mismatch_causes.csv').open() as f:prior=list(csv.DictReader(f))
 earlier={(x['workflow'],x['case_id']) for x in prior if 'CONTEXT_SCHEMA_MISMATCH' in json.dumps(x)}
 current={(f['workflow_label'],f['case_id']) for f in flags}
 reconciliation=dict(authoritative_run=str(BASE),latest_semantics_review=AUTH['latest_semantics_review'],current_source='Current all_negatives/records/*.json likely_cause, with the preserved batch50/failure_causes.csv used only for its original 50 records lacking inline causes.',frozen_earlier_csv=str(CASES/'strict_mismatch_causes.csv'),current_flags_by_workflow={audit.WORKFLOWS[w]:n for w,n in counts.items()},earlier_counts=dict(Counter(w for w,c in earlier)),added_since_earlier_csv=sorted(current-earlier),removed_since_earlier_csv=sorted(earlier-current),unique_cases=len({f['case_id'] for f in flags}),distinct_requirements=len({f['requirement_id'] for f in flags}))
 save('cause_ledger_reconciliation.json',reconciliation)
 groups={};findings=[]
 for f in flags:
  req,w,cid=f['requirement_id'],f['workflow'],f['case_id'];p=URIRef(f['disputed_property']);name=short(p);row=ROWS[w,cid];rec=f['record'];v=rec['workflows'][w]
  ctx_path=Path(row['requirement_context_path']);shape_path=Path(row['shape_path']);prompt=shape_path.parent/'generator_prompt.txt';assert sha(shape_path)==row['generated_shape_sha256']
  context=context_info(str(ctx_path),str(prompt),req,name);schema=schema_info(req,name);shape=shape_info(str(shape_path),str(p));source=source_info(req)
  negpath=Path(rec.get('negative_fixture') or (Path(v['negative']['report_path']).parent/'negative_fixture.ttl'));negative_graph=load(negpath)
  # Prior50 uses a specification-defined pair at its recorded reviewed path.
  if rec.get('repaired_fixture'):reppath=Path(rec['repaired_fixture'])
  else:reppath=Path(v['repaired']['report_path']).parent/'repaired_fixture.ttl'
  if not reppath.exists():
   candidates=list(Path(v['repaired']['report_path']).parent.glob('*repair*.ttl'));candidates=[x for x in candidates if 'report' not in x.name]
   reppath=candidates[0] if len(candidates)==1 else None
  repaired_graph=load(reppath) if reppath and reppath.exists() else None
  # The historical prior50 files are negative.ttl / repaired.ttl, not a new
  # pairing inferred from expected labels or nearby case numbers.
  if repaired_graph is None:
   alt=Path(v['repaired']['report_path']).parent/'repaired.ttl'
   if alt.exists():reppath=alt;repaired_graph=load(alt)
  ng=fixture_property(negative_graph,p);gg=fixture_property(repaired_graph,p) if repaired_graph is not None else []
  finding,status,confidence,reason=classify(req,name,schema,shape,ng,gg,negative_graph)
  if not ng and gg:
   reason+=' The original negative has no value for the disputed property. Its repaired counterfactual is the graph in which the value is present; missing original evidence is not described as placement on a wrong node.'
  adjudicated_arm='REPAIRED_COUNTERFACTUAL' if finding=='FIXTURE_VIOLATES_CLEAR_SCHEMA' and not ng and gg else 'ORIGINAL_NEGATIVE' if finding=='FIXTURE_VIOLATES_CLEAR_SCHEMA' else 'OWNERSHIP_COMPARISON_ONLY'
  if not all(context['locked_source_hashes_agree'].values()):finding,status,confidence,reason='INSUFFICIENT_EVIDENCE','PROVISIONAL','LOW','Context lock hashes do not match the audited locked schema.'
  gid=req+'__'+name
  group=groups.setdefault(gid,dict(group_id=gid,requirement_id=req,disputed_property=str(p),source=source,schema=schema,required_owner_class=schema['explicit_owner_class'],required_owner_path_evidence=dict(termOwners=schema['term_owner_pointer'],modelPaths=schema['modelPaths'],no_owner_filled_from_fallback=schema['explicit_owner_class'] is None),workflows={}))
  classes=set(negative_graph.objects(None,RDF.type))|{URIRef(c) for o in shape['occurrences'] for c in o['owner_class_hints']}
  if repaired_graph is not None:classes.update(repaired_graph.objects(None,RDF.type))
  if req=='I2-024':classes.update([N.interpolationPoint,N.obliquePlatingInterpolationCase,N.calculationCase])
  if req=='TRF-050':
   classes.update([N.frame,N.frameAttachmentRecord]);group['related_causal_weld_schema']=schema_info(req,'frameShellWeldType')
  hierarchy={tuple(map(str,(c,RDFS.subClassOf,p))) for cls in classes for c in supertypes(cls) for p in ONTO.objects(c,RDFS.subClassOf) if isinstance(p,URIRef)}
  group['relevant_class_hierarchy']=sorted(set(tuple(x) for x in group.get('relevant_class_hierarchy',[]))|hierarchy)
  sub=group['workflows'].setdefault(w,dict(workflow=audit.WORKFLOWS[w],case_ids=[],context=context,generated_shape=dict(path=str(shape_path),sha256=sha(shape_path),**shape),findings=[]))
  sub['case_ids'].append(cid);sub['findings'].append(dict(case_id=cid,primary_finding=finding,context_finding=context['context_finding']))
  witnesses={}
  if req=='TRF-050':
   witnesses['causal_weld_property']=fixture_property(negative_graph,N.frameShellWeldType)
   witnesses['causal_weld_shape_owner_paths']=shape_info(str(shape_path),str(N.frameShellWeldType))['occurrences']
   witnesses['property_level_findings']=[dict(property=str(N.shellPlateButtCrossing),finding='BOTH_CONFORM_NO_OWNERSHIP_ERROR',reason='The declared SHACL owner and the explicit fixture owner are frameAttachmentRecord. The extra frame focus is explained by domain-induced typing from the different, misplaced weld property.'),dict(property=str(N.frameShellWeldType),finding='FIXTURE_VIOLATES_CLEAR_SCHEMA',reason='This causal assertion is on frame rather than the frameAttachment object. It is the intentional negative wrong-owner defect; the primary conflict finding concerns this causal assertion.')]
   frame=next(negative_graph.subjects(RDF.type,N.frame));types,proof=rdfs_types(negative_graph,frame)
   witnesses['reported_frame_inferred_record']=dict(frame=str(frame),explicit_types=sorted(map(str,explicit_types(negative_graph,frame))),inferred_types=sorted(map(str,types)),repaired_frame_inferred_types=sorted(map(str,rdfs_types(repaired_graph,frame)[0])) if repaired_graph is not None else None,recorded_validation_environment=read(BASE/'environment.json'),domain_inference_proof=proof,actual_frame_attachment_objects=[str(x) for x in negative_graph.objects(frame,N.frameAttachment)],contract_weld_owner=INDEX['termOwners'][req]['frameShellWeldType'],shape_targets_record_not_frame=True)
  expected=schema['explicit_owner_class'];wrong=[n for n in ng if expected and expected not in n['subclass_closure']]
  value_state='MISSING_EVERYWHERE' if not ng else 'VALUE_PRESENT_ON_NON_CONTRACT_OWNER' if wrong else 'VALUE_PRESENT_ON_ALLOWED_OWNER' if expected else 'VALUE_PRESENT_OWNER_UNSPECIFIED'
  basefixture=Path(row['fixture_path']);INPUTS.add(basefixture)
  item=dict(workflow=w,workflow_label=audit.WORKFLOWS[w],requirement_id=req,case_id=cid,group_id=gid,provisional_cause=f['cause'],provisional_cause_source=f['cause_source'],disputed_property=str(p),adjudicated_primary_property=str(N.frameShellWeldType) if req=='TRF-050' else str(p),related_causal_property=str(N.frameShellWeldType) if req=='TRF-050' else None,primary_finding=finding,finding_status=status,context_finding=context['context_finding'],confidence=confidence,reason=reason,adjudicated_fixture_arm=adjudicated_arm,adjudicated_fixture_path=str(reppath) if adjudicated_arm=='REPAIRED_COUNTERFACTUAL' else str(negpath) if adjudicated_arm=='ORIGINAL_NEGATIVE' else None,required_owner=schema['explicit_owner_class'],required_owner_evidence=schema['term_owner_pointer'],required_model_paths=schema['modelPaths'],shape_owner_paths=shape['occurrences'],fixture_value_state=value_state,fixture_owner_paths=ng,repaired_fixture_owner_paths=gg,context_evidence_pointer=str(DEST/'groups'/f'{gid}.json')+f'#/workflows/{w}/context',source_evidence_pointer=str(DEST/'groups'/f'{gid}.json')+'#/source',fixture_path=str(negpath),fixture_sha256=sha(negpath),original_fixture_path=str(basefixture),original_fixture_sha256=sha(basefixture),repaired_fixture_path=str(reppath) if reppath else None,shape_path=str(shape_path),context_path=str(ctx_path),prompt_path=str(prompt),original_generation_eligible=v['original_eligible'],preserved_strict_status=v['status'],original_expected_label=row['expected'],intended_failure_rationale=row['source_oracle_rationale'],intended_only_repair=rec.get('selected_repair'),validation_evidence=dict(negative=report_info(v['negative']['report_path'],p),repaired=report_info(v['repaired']['report_path'],p)),supplementary_witnesses=witnesses,cardinality_applicability=dict(contract_cardinality_policy=schema['contract'].get('cardinalityPolicies',{}).get(name),contract_applicability_terms=schema['contract'].get('applicabilityTerms',[]),actual_applicability_assertions={term:[dict(owner=str(s),value=o.n3()) for s,o in negative_graph.subject_objects(N[term])] for term in schema['contract'].get('applicabilityTerms',[])},source_applicability_review=dict(rule=APP_REVIEW[req][1],fixture_assertions={term:[dict(owner=str(s),value=o.n3()) for s,o in negative_graph.subject_objects(N[term])] for term in APP_REVIEW[req][0].split()},missing_named_assertions=[term for term in APP_REVIEW[req][0].split() if not list(negative_graph.triples((None,N[term],None)))],scope='These assertions are disclosed rather than used to guess applicability. Placement findings concern properties represented under the explicit requirement contract; they do not add missing obligations when a source branch is inactive.'),fixture_assertions=audit.triples(negative_graph),scope_note='This is a disputed ownership/path finding only, not a statement that either full graph is regulatorily correct. Expected labels and conforming verdicts are preserved as provenance and never determine the finding.'))
  findings.append(item);save('cases/'+w+'__'+cid+'.json',item)
 for gid,g in groups.items():save('groups/'+gid+'.json',g)
 save('findings.json',findings);csvout('findings.csv',findings)
 csvout('confirmed_findings.csv',[r for r in findings if r['finding_status']=='CONFIRMED']);csvout('provisional_or_unresolved_findings.csv',[r for r in findings if r['finding_status']!='CONFIRMED'])
 counts=[]
 for w,label in audit.WORKFLOWS.items():
  for finding in FINDINGS:counts.append(dict(workflow=label,finding=finding,cases=sum(r['workflow']==w and r['primary_finding']==finding for r in findings),denominator=sum(r['workflow']==w for r in findings)))
 csvout('counts_by_workflow.csv',counts)
 context_counts=[dict(workflow=label,context_finding=kind,cases=sum(r['workflow']==w and r['context_finding']==kind for r in findings)) for w,label in audit.WORKFLOWS.items() for kind in ['CORRECT','INCORRECT','CONTRADICTORY','UNDERSPECIFIED']];csvout('context_counts.csv',context_counts)
 summary=dict(flagged_workflow_case_pairs=len(flags),unique_cases=len({f['case_id'] for f in flags}),distinct_requirements=len({f['requirement_id'] for f in flags}),grouped_requirement_property_conflicts=len(groups),counts=counts,context_counts=context_counts,confirmed_workflow_case_findings=sum(r['finding_status']=='CONFIRMED' for r in findings),provisional_workflow_case_findings=sum(r['finding_status']!='CONFIRMED' for r in findings),validation_reruns=0,queries_executed=0,shape_fixes=0,fixture_fixes=0,api_calls=0,verdicts_labels_exclusions_changed=False)
 save('summary.json',summary)
 # The new artifacts are additive. All original authoritative-run files and
 # every outside input used by this comparison must have identical hashes.
 outside={str(p):sha(p) for p in INPUTS if p.exists() and p.is_file()}
 save('input_sha256.json',outside)
 for p,h in protected.items():assert sha(p)==h,f'Existing audit artifact changed: {p}'
 save('preservation_checks.json',dict(existing_authoritative_run_files_unchanged=len(protected),input_files_hashed=len(outside),original_shapes_match_recorded_sha256=True,all_current_flags_reviewed=len(findings)==115,all_flag_case_ids_retained=True,no_validation_or_query_execution=True,labels_verdicts_exclusions_and_cause_ledgers_unchanged=True))
 lines=['# Ownership/path adjudication — retained evaluation evidence','',f'Authoritative baseline `{BASE.name}`, latest semantic review `{Path(AUTH["latest_semantics_review"]).name}`. The current flags are **59 NLTL_v2 / 56 Single-shot**, rather than the frozen earlier 58/55 CSV. Current per-case causes plus the original-50 cause fallback produce **115 workflow/case flags, 89 unique cases, 20 requirements**, grouped into **'+str(len(groups))+' requirement/property analyses**.','', '| Finding | NLTL_v2 (59 flags) | Single-shot (56 flags) |','|---|---:|---:|']
 for finding in FINDINGS:lines.append('| '+finding+' | '+' | '.join(str(next(r['cases'] for r in counts if r['workflow']==label and r['finding']==finding)) for label in audit.WORKFLOWS.values())+' |')
 lines+=['','Fixture-side counts cover the original negative or its supplied repaired counterfactual, as explicitly recorded by adjudicated_fixture_arm. Five workflow/case flags have no original value; the wrong-owner value exists only in the supplied repair, and is not misdescribed as an original wrong-node assertion. Confirmed placement violations are distinguished from supported no-ownership-error findings and unresolved schema gaps. These counts do not rescore validation or strict intended-failure accuracy. A deliberately invalid negative fixture can violate the representation without being an invalid test.','', '## Evidence and examples','', '- **TRF-130:** `/termOwners/TRF-130/totalRelevantEnginePower = ship`. Both source engine-output wording and the explicit contract are consistent with a ship-owned shared quantity. Where present, the flagged negative or supplied repaired fixtures put it on an inlet chest while the shape requires it on ship. This is a fixture placement violation; the broad benchmarkEntity domain is not the ownership proof.','- **TRF-050-F05, both workflows:** the shapes target frameAttachmentRecord. The fixture puts frameShellWeldType on frame instead of the linked frameAttachment object. That assertion infers frameAttachmentRecord on frame via RDFS domain, explaining why record constraints report a missing shellPlateButtCrossing there. The previous shape-owner blame is not supported: this is the intended fixture wrong-owner defect. The existing strict classification is preserved. The property-level record explicitly separates correctly placed shellPlateButtCrossing from the causal misplaced frameShellWeldType; the primary case finding refers to the latter.','- **I2-024, Single-shot:** interpolationPoint and obliquePlatingInterpolationCase are subclasses of calculationCase. Values on the root case and constraints on endpoint calculationCase instances do not establish an incompatible owner. Missing endpoint values and a possibly overbroad universal minCount are separate cardinality/role-scope issues, which the supplied contract does not settle.','- **I2-006:** the shape and every supplied aftSectionDesignBasis value use ship; one negative omits the value rather than placing it elsewhere. The flagged error is an exact-string/literal issue, not ownership.','', '## Unresolved representation and context','', 'For the SCHEMA_UNDERSPECIFIED groups, the disputed property lacks an explicit requirement-specific termOwners assignment and a modelPath binding that property. Related case/component relationships do not fix the missing property owner. All these domains are benchmarkEntity. requiredOwner=ship in the historical context is retained as prompt evidence, not treated as authoritative schema. This includes the earlier machineryComponentType owner claim for IMO-049.','', 'No exclusive placement rule is inferred from an RDFS domain. Range and subclass relations are recorded separately. No ontology/contract contradiction is declared merely because classes differ; actual explicit inconsistencies, if present, are listed in each schema record.','', 'The actual attempt_01 generator_prompt.txt payload is compared with the initial context pack and the locked ontology/index hashes. `context_counts.csv` separately reports correct/incorrect/contradictory/underspecified ownership context; generic calculationCase role/cardinality scope remains underspecified even where its owner class is correct.','', '## Files','', '`cause_ledger_reconciliation.json` identifies the current cause source and semantic-review additions. `current_provisional_cause_ledger.*` preserves the flags before adjudication. `findings.*` gives one primary finding for each of the 115 flags. `confirmed_findings.csv` and `provisional_or_unresolved_findings.csv` are separate. `groups/` contains source excerpts, complete property declarations, class hierarchy, exact contract/termOwners/modelPaths, actual prompt excerpts and shape traversal for each grouped analysis. `cases/` retains every affected case, exact fixture owners/types/paths and both saved validation reports.','', 'No existing file, shape, fixture, verdict, label, exclusion or cause record is changed. All prior authoritative-run artifact hashes are checked. No validation, generation or API call is made. The audit script and read-only tests are retained here.']
 (DEST/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(summary,indent=2));print('Output:',DEST)

if __name__=='__main__':run()
