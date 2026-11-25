import pathlib,json,hashlib,copy,socket,shutil,subprocess,time,collections
R=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');M=R.parent/'MVP';O=R/'outputs/audits/20261124_FIVE_REQUIREMENT_SCOPE_READINESS'
B=M/'SHACL_GENERATION_PIPELINE/evaluation/BEHAVIORAL_RDF_R13'
PREV=R/'outputs/audits/20261124_V0101_REPAIR_ASSESSMENT_FRESH_PILOT_PREPARATION/pilot_preparation'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
assert not O.exists()
before={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
O.mkdir(parents=True);write(O/'protected_before.json',before)
catpath=R/'data/requirements/source_catalog.json';shutil.copy2(catpath,O/'source_catalog.before.json');catalog=load(catpath)
# Verify retained publisher-imprint documents and full, byte-identical extraction offline.
metadata=[('Ice Class Regulations and the Application Thereof','TRAFICOM.pdf','TRAFICOM_68863_2021.pdf','TRAFICOM/68863/03.04.01.00/2021','2021 regulation (issued 1 July 2021)','Finnish Transport and Communications Agency Traficom','5 July 2021',dict(edition_evidence='Page 1 regulation identifier and issued/entry-into-force table; page 5 section 1.1 identifies the 2021 regulations.',applicability_evidence='Section 1.1: contracted for construction on/after 5 July 2021; section 1.8 and chapter 2 apply irrespective of build year. Distinct section/transition rules remain source context.')),
('International Code for Ships Operating in Polar Waters (Polar Code)','MSC.385(94).pdf','MSC_385_94_2014.pdf','MSC.385(94)','Resolution MSC.385(94) (adopted 21 November 2014)','International Maritime Organization, Maritime Safety Committee','1 January 2017',dict(edition_evidence='PDF page 2: resolution adopted 21 November 2014; operative paragraph 1 adopts safety-related Introduction and parts I-A/I-B.',applicability_evidence='Operative paragraph 3 states effect on 1 January 2017 upon SOLAS chapter XIV entry into force. This is not a current consolidated Polar Code edition or a complete environmental-code adoption.')),
('Polar Code January 2026 Supplement - Resolution MSC.538(107)','POLARCODES.pdf','Polar_Code_January_2026_Supplement.pdf','MSC.538(107)','January 2026 supplement to Polar Code 2016 Edition','International Maritime Organization, Maritime Safety Committee','1 January 2026',dict(edition_evidence='Page 1: January 2026 Supplement, Resolution MSC.538(107), adopted 8 June 2023, amendments entering into force 1 January 2026.',applicability_evidence='Supplement to 2016 edition, not the full consolidated Code. Not selected for the five-requirement pilot.'))]
source_checks=[]
for title,original,dest,docid,edition,authority,effective,extra in metadata:
 src=M/'RELEVANT FILES'/original;raw=subprocess.run(['pdftotext','-layout',str(src),'-'],capture_output=True,check=True).stdout
 entry=catalog['sources'][title];assert raw==(R/entry['file']).read_bytes(),title
 out=R/'data/requirements/originals'/dest;assert not out.exists();shutil.copy2(src,out)
 entry.update(document_id=docid,aliases=[docid],authority=authority,edition=edition,effective_date_as_printed=effective,governing_edition_status='NOT_DETERMINED',provenance=dict(kind='Retained publisher-imprint PDF, verified offline; no online retrieval or current-law certification',file=str(out.relative_to(R)),sha256=sha(out),retained_origin='MVP/RELEVANT FILES/'+original,extraction='pdftotext -layout; entire extracted UTF-8 output byte-identical to retained source text',extraction_tool=subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.strip().splitlines()[0],extraction_sha256=hashlib.sha256(raw).hexdigest(),visual_verification='TRAFICOM page 1; MSC.385(94) pages 1-2; January 2026 supplement page 1 inspected',missing_information=['Original acquisition URL/date and download chain not established from retained records.','No determination of legally governing edition for an actual vessel.'],**extra))
 source_checks.append(dict(document_id=docid,source_text=entry['file'],source_sha256=sha(R/entry['file']),pdf=str(out.relative_to(R)),pdf_sha256=sha(out),exact_full_extraction_match=True,governing_edition_selected=False))
write(catpath,catalog);write(O/'source_metadata_verification.json',source_checks)
for name in ['TRAFICOM_title','IMO_resolution','IMO26_title']:shutil.copy2(pathlib.Path('/tmp/nltl-readiness-pdfs')/(name+'.png'),O/(name+'.png'))
from nltlv2.core import Project,GenerationProject
from nltlv2.schema import Schema,N,Q,U
from nltlv2.admission import validate_declaration,definition_hash,checksum,POLICY
from nltlv2.requests import initial_request
from nltlv2.prompt_accounting import measure
from nltlv2.evidence import literal_identity
from rdflib import Graph,RDF,RDFS,URIRef
from owlrl import DeductiveClosure,RDFS_Semantics
p=Project(R);s=Schema(p);approved=load(R/'data/admissions/i2_004_research_scope.approved.json');approved_result=validate_declaration(approved,s,'I2-004');assert approved_result['valid']
common='Synthetic ship-design records supplied as the complete nltl:ship population of each input. External legal/application eligibility and the experimental source-edition selection are research assumptions, not facts inferred from RDF. This is not real-vessel certification. The population includes incomplete, inconsistent and unrecognized-value records; represented correctness is not assumed. Conditions inside the represented requirement, effective activation, missing represented inputs, paths, units, datatypes and query correctness remain for generated SHACL to address from supplied source/schema. '
scopes={};scope_paths={};validation=[]
primary_titles={rid:s.requirements[rid]['source'] for rid in ['I2-005','IMO-001','TRF-010','TRF-035']}
descriptions={
'I2-005':'The represented domain is the I2.2.5 bottom/lower-region boundary on externally assumed Polar Class design records. Linked hull-boundary-point records and inclination quantities are supplied observations/claims about this boundary. This does not independently reconstruct a hull surface or verify that the submitted point set is physically complete. The source-defined boundary condition remains in scope; its satisfaction is not an eligibility assumption.',
'IMO-001':'The represented domain is Polar Code Introduction 2.1 design-condition/category records externally assumed within the selected safety-related Code research population. The supplied controlled design-condition value is a record of design intent, not independently measured ice-navigation capability. No particular category or design condition is assumed true for every record; source conditions and unavailable selector information remain generated-validation/review responsibilities.',
'TRF-010':'The represented domain is section 1.8 ice-class designation records, not an independent reconstruction of structure, propulsion power or navigational capability. External research eligibility is assumed for the supplied records; section 1.1 expressly applies section 1.8 irrespective of year of build. Designation validity is not assumed, and the source descriptions remain visible. No proof of an actual ship\'s class assignment or underlying capabilities is claimed.',
'TRF-035':'The represented domain is section 4.1.1 L records for synthetic designs externally assumed eligible for the selected 2021 regulation, including its construction-date/application scope. The proposed data-role interpretation is that ruleLength records L used by the design and classificationSocietyRuleLength records a separately supplied classification-society reference quantity. Both are existing direct ship-owned quantities in canonical metres/decimal encoding. Authenticity of the external society datum is assumed for research, not calculated or certified from a society-name string. No relationship between their values is assumed in this admission; the source obligation remains for generated SHACL.'}
for rid in primary_titles:
 entries=[catalog['sources'][primary_titles[rid]]]
 if rid=='I2-005':entries.append(catalog['sources']['UR I1 Polar Class Descriptions and Application'])
 decl=dict(format_version=2,admission_id='SYNTHETIC_DESIGN_RESEARCH_SCOPE_'+rid.replace('-','_')+'_V1',interpretation='A',population_description=common+descriptions[rid],focus_set=dict(mode='COMPLETE_CLASS_POPULATION_PER_INPUT',owner_class=str(N.ship)),eligibility_assertion='ASSUMED_EXTERNAL_RESEARCH_ELIGIBILITY',provenance=dict(declarant='Assistant-prepared proposal at user request; not caller approval',reference='Offline five-requirement readiness proposal, 2026-11-24',basis='Proposed synthetic record population; no admission inferred from expected labels, generated shapes or performance.'),source_editions=[{k:e[k] for k in ['document_id','edition','file','sha256']}|dict(selection_provenance='Proposed experimental use of retained source identity, verified offline on 2026-11-24. Not approved by the caller and not a governing-edition determination.') for e in entries],approval=dict(status='PROPOSED_NOT_APPROVED',approved_by='No approval recorded',reference='Prepared for explicit grouped caller decision; not approved by this preparation.'))
 path='data/admissions/'+rid.lower().replace('-','_')+'_research_scope.proposed.json';assert not (R/path).exists();write(R/path,decl);scopes[rid]=decl;scope_paths[rid]=path
 v=validate_declaration(decl,s,rid);assert not v['valid'];assert all(e['path']=='$.approval' for e in v['errors']),v
 validation.append(dict(requirement_id=rid,file=path,sha256=sha(R/path),scope_definition_sha256=definition_hash(decl),valid=False,errors=v['errors'],interpretation='Only real approval missing; no approval simulated or invented.'))
scopes['I2-004']=approved;scope_paths['I2-004']='data/admissions/i2_004_research_scope.approved.json'
write(O/'scope_validation.json',validation)
# A mapping proposal only: no equality, formulas, required values or expected verdicts.
mapping=dict(status='PROPOSED_DECISION_NOT_INSTALLED',requirement_id='TRF-035',ambiguity='The source defines a single L. Existing ontology offers ruleLength and classificationSocietyRuleLength, but broad quantity/ownership declarations alone do not distinguish an L record from a society reference or establish whether they are aliases. Generic development annotations and a society-name string cannot establish independent provenance.',options=[dict(id='A',recommendation='RECOMMENDED',decision='Retain the two existing distinct properties as separate supplied data roles.',roles={'ruleLength':'Recorded L used by the design','classificationSocietyRuleLength':'Separately supplied society rule-length reference datum'},mapping_facts={'owner':'ship','range':str(Q.QuantityValue),'numeric_predicate':str(Q.numericValue),'numeric_datatype':'http://www.w3.org/2001/XMLSchema#decimal','unit_predicate':str(Q.unit),'unit':str(U.M)},reason='Smallest interpretation consistent with existing explicit ownership, quantity declarations and source wording; no schema or checker change required. Source/schema judgments remain reviewed interpretations.'),dict(id='B',decision='Treat both fields as aliases for a single datum.',consequence='Current two-field evaluation construction would not test independent source/reference consistency; requires a separately authorized representation/evaluation redesign. Do not infer owl:equivalentProperty.'),dict(id='C',decision='Require independent classification-society documents and explicit provenance before admitting any supplied reference value.',consequence='Current synthetic fixtures do not contain such evidence; TRF-035 would remain blocked under that stronger scope.')],not_encoded=['equality rule','formula','expected verdict','classification-society calculation','obligatory adjacent hull-region geometry'],production_mapping_unchanged=True)
write(O/'trf_035_mapping_decision.proposed.json',mapping)
# Evaluation-only construction ancestry; no expected verdict or generated performance consulted.
selection=load(R/'evaluation/selections/regression_core.json');rids=['I2-004','I2-005','IMO-001','TRF-010','TRF-035'];cases=[c for c in selection['cases'] if c['requirement_id'] in rids]
migration_path=R/'docs/history/migration_manifest.json';migration={e['destination']:e for e in load(migration_path)['files']}
batches={'I2-004':'i2_batch_g','I2-005':'i2_batch_g','IMO-001':'imo_batch_a','TRF-010':'traficom_batch_a','TRF-035':'traficom_batch_d'}
batch_data={}
for batch in set(batches.values()):
 mf=B/'manifests'/(batch+'_manifest.jsonl');lf=B/'locks'/(batch+'_fixture_lock.json');lock=load(lf);assert lock['frozen_files']['manifests/'+mf.name]==sha(mf)
 batch_data[batch]=(mf,lf,lock,{row['case_id']:row for row in [json.loads(l) for l in mf.read_text().splitlines() if l.strip()]})
rows=[];population_start=time.monotonic()
for c in cases:
 rid=c['requirement_id'];decl=scopes[rid];mf,lf,lock,manifest=batch_data[batches[rid]];ancestry=manifest[c['case_id']];assert ancestry['requirement_id']==rid
 for kind in ['fixture','counterfactual']:
  if not c.get(kind):continue
  path=c[kind];f=R/path;h=sha(f);migration_row=migration[path];origin=R.parent/migration_row['source'];assert origin.is_file() and sha(origin)==migration_row['source_sha256']==h
  if kind=='fixture':assert lock['frozen_files'][ancestry['rdf_path']]==h and sha(B/ancestry['rdf_path'])==h
  with literal_identity():g=Graph().parse(f)
  explicit=sorted(str(x) for x in g.subjects(RDF.type,N.ship));assert explicit
  merged=Graph()
  for graph in [s.graph,g]:
   for t in graph:merged.add(t)
  DeductiveClosure(RDFS_Semantics).expand(merged)
  actual=sorted(set(str(x) for x in merged.subjects(RDF.type,N.ship)));assert actual==explicit,(path,actual,explicit)
  refs=['Reviewed offline construction ancestry and represented population, 2026-11-24; not approval or conformance certification.','docs/history/migration_manifest.json',str(O.relative_to(R))+'/evaluation_construction_review.json#'+c['case_id']+'/'+kind]
  binding=dict(format_version=1,scope_id=decl['admission_id'],scope_definition_sha256=definition_hash(decl),input_sha256=h,admitted_nodes=actual,construction_provenance=dict(kind='SYNTHETIC_CONSTRUCTION_REVIEWED',references=refs))
  bindingfile=O/'evaluation_only_bindings'/rid/(c['case_id']+('.repaired' if kind=='counterfactual' else '')+'.admission.json');write(bindingfile,binding)
  quantities=[dict(node=str(node),numeric_values=[v.n3() for v in g.objects(node,Q.numericValue)],units=[str(v) for v in g.objects(node,Q.unit)]) for node in set(g.subjects(RDF.type,Q.QuantityValue))]
  rows.append(dict(requirement_id=rid,case_id=c['case_id'],kind=kind,file=path,input_sha256=h,migration_origin=migration_row['source'],migration_origin_sha256=sha(origin),migration_hash_match=True,construction_manifest=str(mf.relative_to(M)),construction_manifest_sha256=sha(mf),original_lock=str(lf.relative_to(M)),original_lock_sha256=sha(lf),original_fixture_lock_matches=True if kind=='fixture' else None,construction_claim={k:ancestry[k] for k in ['source_id','source_clause','verification_mode','sourceability_grade','generated_shacl_inspected'] if k in ancestry},declared_population_nodes=actual,rdfs_population_equals_declared=True,quantities=quantities,binding_file=str(bindingfile.relative_to(R)),prospective_compatibility='SUPPORTED_FOR_EXISTING_APPROVED_SCOPE' if rid=='I2-004' else 'SUPPORTED_CONDITIONAL_ON_ACTUAL_SCOPE_APPROVAL'+('_AND_MAPPING_OPTION_A' if rid=='TRF-035' else ''),real_vessel_eligibility_verified=False,expected_labels_consulted_for_admission=False,generated_shapes_or_results_consulted=False))
  if len(rows)%10==0:print('Reviewed prospective population',len(rows),'of 46 inputs',flush=True)
write(O/'evaluation_construction_review.json',dict(status='CONSTRUCTION_AND_PROSPECTIVE_SCOPE_COMPATIBILITY_REVIEW_ONLY',inputs=len(rows),fixtures=sum(x['kind']=='fixture' for x in rows),counterparts=sum(x['kind']=='counterfactual' for x in rows),no_conformance_evaluation=True,no_approval_inferred=True,labels_consulted_for_admission=False,source_ancestry_independent_of_current_performance=True,runtime_seconds=time.monotonic()-population_start,limitations=['Historical manifests assert construction without inspecting generated SHACL; this is retained provenance, not newly certified blindness or held-out status.','Scope eligibility is a proposed external research assumption, never certified by file hashes or labels.','Population/record compatibility does not prove source obligations or expected labels correct.','Incomplete and wrong-unit/unknown-value records remain in population and are not filtered out for failing represented requirements.'],rows=rows))
# Inspect counterparts as data construction edits, not conformance testing.
pairs=[]
for c in cases:
 if not c.get('counterfactual'):continue
 with literal_identity():g=Graph().parse(R/c['fixture']);h=Graph().parse(R/c['counterfactual'])
 pairs.append(dict(case_id=c['case_id'],requirement_id=c['requirement_id'],removed=sorted(' '.join(v.n3() for v in t) for t in set(g)-set(h)),added=sorted(' '.join(v.n3() for v in t) for t in set(h)-set(g)),scope_population_preserved=sorted(map(str,g.subjects(RDF.type,N.ship)))==sorted(map(str,h.subjects(RDF.type,N.ship))),note='Actual graph edit evidence; no expected verdict inferred from admission.'))
write(O/'evaluation_only_counterpart_edits.json',pairs)
# Matched initial request previews. Unapproved declarations are never turned into approved contexts.
sizes=[];configs=[]
for rid in rids:
 decl=scopes[rid];context=s.context(rid)
 context['admission']=copy.deepcopy(approved_result['context']) if rid=='I2-004' else dict(declaration=copy.deepcopy(decl),declaration_sha256=checksum(decl),scope_definition_sha256=definition_hash(decl),policy=POLICY,verification='PROPOSED common experimental scope preview only. No approval or dispatch authorized.')
 context['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 reqs=[]
 for method in ['NLTL','Single-shot']:
  cfg=load(PREV/(rid+'_'+method+'_PROPOSED.json'));cfg['admission_file']=scope_paths[rid];cfg['method']='offline';cfg['network_enabled']=False;cfg['proposal_only']=True
  configfile=O/'pilot_configs'/(rid+'_'+method+'_PROPOSED.json');write(configfile,cfg);p.config(str(configfile.relative_to(R)))
  settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']};req=initial_request(GenerationProject(R),copy.deepcopy(context),settings);reqs.append(req)
  write(O/'initial_request_previews'/(rid+'_'+method+'_OFFLINE_ONLY.json'),req)
 assert reqs[0]==reqs[1]
 assert all(c['case_id'] not in reqs[0]['system']+reqs[0]['user'] for c in cases)
 row=measure(reqs[0]);row.update(requirement_id=rid,identical_between_arms=True,includes_proposed_admission=rid!='I2-004',status='EXACT_CURRENT_APPROVED_INITIAL_RENDER' if rid=='I2-004' else 'EXACT_PROPOSED_UNAPPROVED_PREVIEW_NOT_DISPATCHABLE',user_sha256=hashlib.sha256(reqs[0]['user'].encode()).hexdigest(),system_sha256=hashlib.sha256(reqs[0]['system'].encode()).hexdigest());sizes.append(row)
write(O/'paired_request_sizes.json',sizes)
plan=load(PREV/'plan.json');plan.update(status='OFFLINE_PREPARATION_COMPLETE_AWAITING_GROUPED_SCOPE_AND_MAPPING_APPROVAL',admission_files=scope_paths,source_catalog_sha256=sha(catpath),request_sizes_file=str((O/'paired_request_sizes.json').relative_to(R)),scope_approval_does_not_authorize_dispatch=True,evaluation_bindings_status='Prepared outside production; new scopes remain unapproved; no conformance evaluation performed.',deferred=['I2-042']);write(O/'pilot_plan.proposed.json',plan)
allowed={'data/requirements/source_catalog.json'}
changed=[k for k,h in before.items() if not (R/k).is_file() or sha(R/k)!=h];assert set(changed)==allowed,changed
write(O/'preservation_verification.json',dict(status='PASS',existing_files_checked=len(before),only_authorized_existing_file_change=changed,all_other_existing_files_unchanged=True,implementation_prompts_schema_approved_scope_historical_runs_scores_fixtures_tracker_ledger_unchanged=True,network_calls=0,provider_calls=0,conformance_evaluation_reruns=0,source_texts_unchanged=True))
shutil.copy2('/tmp/nltl_complete_readiness.py',O/'offline_readiness_driver.py')
print(json.dumps(dict(output=str(O),inputs=len(rows),pairs=len(pairs),sizes=[dict(requirement_id=x['requirement_id'],bytes_per_arm=x['rendered_bytes']) for x in sizes],changed_existing=changed,protected=len(before)),indent=2),flush=True)
