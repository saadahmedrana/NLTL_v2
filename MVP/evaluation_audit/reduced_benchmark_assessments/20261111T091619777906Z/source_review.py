"""Independent source/schema certification; no workflow outcomes are inputs."""
import sys,copy,json
from pathlib import Path
from decimal import Decimal
from datetime import date
from collections import defaultdict,Counter
from rdflib import Graph,URIRef,Literal,RDF,XSD
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D))
import source_inventory as m
N,Q,U=m.N,m.Q,m.U

PLANS={
'I2-004':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='Selected UIWL displacement equals max of represented waterline-case displacements.',scope='Static represented cases; not independent measurement of ship displacement.',branches={'multiple_maximum_positive':['I2-004-G-P01','I2-004-G-P02'],'single_case_positive':['I2-004-G-P03'],'nonmaximum_negative':['I2-004-G-F01'],'missing_result':['I2-004-G-F02'],'wrong_unit':['I2-004-G-F03']},gaps=['No exhaustive ties, malformed input-case, or multiple selected-value tests; not claimed as exhaustive robustness coverage.']),
'I2-005':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='A represented bottom/lower-region boundary point has shell inclination exactly 7 degrees.',scope='Approved sampled-boundary-point representation; not geometric verification of the entire hull boundary.',branches={'equal_7_positive':['I2-005-G-P01'],'below_7_negative':['I2-005-G-F01'],'above_7_negative':['I2-005-G-F02'],'wrong_unit':['I2-005-G-F03'],'missing_boundary_point':['I2-005-G-F04']},gaps=['Missing numeric subfield and multiple boundary points are not separately tested; no whole-hull geometric claim.']),
'I2-042':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='For every represented structural member, flangeWidth >= 5 * netWebThickness (minimum, not maximum).',scope='Universal inequality over represented member inventory; empty inventory is not an existence failure.',branches={'boundary_positive':['I2-042-G-P01'],'above_positive':['I2-042-G-P02'],'empty_inventory_positive':['I2-042-G-P03'],'below_negative':['I2-042-G-F01'],'missing_width':['I2-042-G-F02'],'missing_web':['I2-042-G-F03'],'wrong_unit':['I2-042-G-F04']},gaps=['No mixed good/bad multi-member fixture; universal-loop robustness is not exhaustive.']),
'IMO-001':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='designIceCondition=mediumFirstYearIceWithPossibleOldIceInclusions implies shipCategory=A; missing selector is a locked representation-readiness violation.',scope='Approved controlled design-condition/category mapping; no engineering certification of design capability.',branches={'applicable_positive':['IMO-001-P01'],'nonapplicable_positive':['IMO-001-P02'],'wrong_category':['IMO-001-F01'],'missing_category':['IMO-001-F02'],'missing_selector':['IMO-001-F03']},gaps=['Other nonapplicable controlled conditions and multivalued selectors are not separately tested.']),
'TRF-010':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='Assigned ice class is one of IA Super, IA, IB, IC, II, III.',scope='Canonical six-value ice-class representation.',branches={'IA_Super':['TRF-010-P01'],'IA':['TRF-010-P02'],'IB':['TRF-010-P03'],'IC':['TRF-010-P04'],'II':['TRF-010-P05'],'III':['TRF-010-P06'],'unknown_negative':['TRF-010-F01'],'missing_class':['TRF-010-F02']},gaps=['Multiple simultaneous class assignments are not separately tested; no new exclusivity/cardinality policy is inferred.']),
'TRF-035':dict(status='DEFENSIBLE_REPRESENTED_CORE',law='ruleLength equals classificationSocietyRuleLength, both canonical metre quantities.',scope='Transfer/comparison of represented rule length, not independent classification-society calculation.',branches={'equality_value_one':['TRF-035-P01'],'equality_value_two':['TRF-035-P02'],'inequality_negative':['TRF-035-F01'],'missing_input':['TRF-035-F02'],'missing_result':['TRF-035-F03'],'wrong_unit':['TRF-035-F04']},gaps=['No arbitrary unit-conversion alternatives or multivalued input tests; only canonical schema representation.']),
'TRF-001':dict(status='PARTIAL_BRANCH_COVERAGE',law='From 2021-07-05 apply 2021 edition; both specified universal 2021 provisions apply on both sides of cutoff.',scope='Corrected universal assertions and date-dependent represented edition.',branches={'at_cutoff':['TRF-001-P01'],'after_cutoff':['TRF-001-P02'],'before_cutoff':['TRF-001-P03'],'wrong_postcutoff_edition':['TRF-001-F01'],'missing_date_readiness':['TRF-001-F02'],'missing_universal_section_1_8':[],'missing_universal_chapter_2':[]},gaps=['All fixtures now include universal provisions; there is no negative isolating omission of either provision. Do not freeze this requirement as branch-complete.']),
'TRF-050':dict(status='PARTIAL_BRANCH_COVERAGE',law='Every linked attachment record has doubleContinuousWeld; scalloping is forbidden except at shell-plate butt crossing.',scope='Explicit Frame -> frameAttachment -> frameAttachmentRecord model. RDFS consequences of F05 are intentional, not unrelated fixture defects.',branches={'no_crossing_positive':['TRF-050-P01'],'crossing_exception_positive':['TRF-050-P02'],'scalloping_away_from_crossing':['TRF-050-F01'],'wrong_weld_no_crossing':['TRF-050-F02'],'missing_weld':['TRF-050-F03'],'missing_scalloping':['TRF-050-F04'],'wrong_weld_owner':['TRF-050-F05'],'wrong_weld_with_crossing':[],'missing_crossing_selector':[]},gaps=['No isolated wrong-weld negative inside the crossing exception branch; no missing-crossing-selector readiness negative. F05 remains valid.']),
'TRF-058':dict(status='UNRESOLVED_APPLICABILITY_BINDING',law='Outside the ice belt, adjustedForce = force*(1-hs/ls).',scope='Represented formula only; not structural load derivation.',branches={'outside_formula_positive':['TRF-058-P01'],'hs_zero_positive':['TRF-058-P02'],'wrong_adjustment':['TRF-058-F01'],'missing_hs':['TRF-058-F02'],'missing_adjustment':['TRF-058-F03'],'wrong_unit':['TRF-058-F04'],'inside_belt_nonapplicable_positive':[]},gaps=['A supportedStringerOutsideIceBelt selector or a source-backed derivation of applicability must be established; source/contract does not authorize treating absence as false. No nonapplicable positive.']),
}

TRANSCRIPTION=m.read(m.HERE/'source_review/table8_transcription.json')
GRADE_NAMES={'B':'steelGradeB','D':'steelGradeD','E':'steelGradeE','AH':'steelGradeAh','DH':'steelGradeDh','EH':'steelGradeEh','FH':'steelGradeFh'}
SOURCE_GROUPS={'PC1-5':{1,2,3,4,5},'PC6-7':{6,7},'PC1-3':{1,2,3},'PC4-5':{4,5}}
PLANS['I2-048']=dict(status='PARTIAL_TABLE_COVERAGE_AND_PENDING_REPAIR',law='Select the general Table-8 source cell by thickness band, Polar Class group, material class and strength family; required grade matches that cell, actual grade is at least that rank. NA is not a grade.',scope='Source-transcribed generic Table-8 selections only. Special single-strake footnote-2 allowance is not represented or claimed.',branches={'source_cell_positive_matrix':[],'all_selector_value_and_exception_negative_controls':[]},gaps=['Source cell positives do not by themselves prove negative coverage of each selector group. One original duplicate-material test has no existing reviewed repair. Footnote-2 allowance is outside the represented generic table model.'])
PLANS['TRF-036']=dict(status='PARTIAL_TABLE_BRANCH_CONTROLS_AND_AMBIGUOUS_CASE',law='Ship-owned iceClass selects Table-4-1 design parameters: IA Super (1.0,0.35), IA (0.8,0.30), IB (0.6,0.25), IC (0.4,0.22) metres.',scope='Stored design-parameter constants, not measured actual sea-ice thickness.',branches={'IA_Super_positive':['TRF-036-P01'],'IA_positive':['TRF-036-P02'],'IB_positive':['TRF-036-P03'],'IC_positive':['TRF-036-P04'],'wrong_IA_hi':['TRF-036-F01'],'wrong_IB_h':['TRF-036-F02'],'missing_selector':['TRF-036-F03'],'missing_ship_path':['TRF-036-F04'],'non_table_class_expectation_unresolved':['TRF-036-F05'],'wrong_unit':['TRF-036-F06'],'IA_Super_bad_parameter':[],'IC_bad_parameter':[]},gaps=['Source does not establish a Table-4-1 parameter mapping for class II; F05 must not be called valid merely because an old oracle rejects it. No wrong-parameter negative in IA Super or IC branches.'])


def fresh_oracle(g,req):
 defects=[];witness=[];unresolved=[]
 def fail(prop,why):defects.append(dict(property=prop,reason=why))
 def one(s,prop,required=True):
  vals=list(g.objects(s,N[prop]));witness.append(dict(owner=str(s),property=prop,values=[v.n3() for v in vals]))
  if not vals:
   if required:fail(prop,'MISSING')
   return None
  if len(vals)>1:unresolved.append(dict(property=prop,reason='MULTIVALUED_BINDING_NOT_ADJUDICATED'));return None
  return vals[0]
 def quantity(s,prop,unit):
  node=one(s,prop)
  if node is None:return None
  nums=list(g.objects(node,Q.numericValue));units=list(g.objects(node,Q.unit))
  if len(nums)!=1 or not isinstance(nums[0],Literal) or nums[0].datatype!=XSD.decimal:fail(prop,'CANONICAL_DECIMAL_REQUIRED');return None
  if units!=[unit]:fail(prop,'WRONG_CANONICAL_UNIT');return None
  return Decimal(str(nums[0]))
 def objects_of_class(cls):return [n for n in set(g.subjects(RDF.type,None)) if N[cls] in m.types(g,n)]
 ships=objects_of_class('ship')
 if req not in ['TRF-050','TRF-058'] and len(ships)!=1:return dict(conforms=None,defects=[],unresolved=[dict(reason='SHIP_IDENTITY_UNRESOLVED')],witness=[])
 ship=ships[0] if ships else None
 if req=='I2-048':
  pcs=list(g.objects(ship,N.polarClass));cases=list(g.objects(ship,N.hasSteelGradeRequirementCase))
  if cases and len(pcs)!=1:fail('polarClass','MISSING_OR_AMBIGUOUS_SOURCE_SELECTOR')
  if cases and len(pcs)==1:
   try:pc=int(str(pcs[0]).split('polarClassPc')[-1])
   except Exception:pc=None
   for case in cases:
    plate=one(case,'steelGradeRequirementCasePlating');thickness=quantity(case,'asBuiltPlateThickness',U.MilliM);material=one(case,'steelMaterialClass');family=one(case,'steelStrengthCategory');ref=one(case,'tableReference');actual=one(case,'actualHullStructuralSteelGrade')
    required=list(g.objects(case,N.requiredHullStructuralSteelGrade))
    # These exact cardinalities are explicitly present in the locked contract.
    for prop in ['steelMaterialClass','tableReference']:
     if len(list(g.objects(case,N[prop])))>1:
      unresolved[:]=[x for x in unresolved if x.get('property')!=prop]
      fail(prop,'EXPLICIT_LOCKED_MAXCOUNT_ONE')
    if ref is not None and ref!=N.iacsUrI2Table8:fail('tableReference','NOT_CANONICAL_TABLE8_REFERENCE')
    if thickness is None or material is None or family is None or pc is None:continue
    row=next((i for i,upper in enumerate(TRANSCRIPTION['upper_inclusive_mm']) if thickness<=Decimal(str(upper))),None)
    cols=[i for i,col in enumerate(TRANSCRIPTION['columns']) if str(material)==str(N[col['steelMaterialClass']]) and str(family)==str(N[col['steelStrengthCategory']]) and pc in SOURCE_GROUPS[col['polarClassGroup']]]
    if row is None or len(cols)!=1:unresolved.append(dict(reason='SOURCE_TABLE_CELL_NOT_UNIQUELY_ESTABLISHED'));continue
    grade=TRANSCRIPTION['grades'][row][cols[0]]
    witness.append(dict(source_table_row=row,source_table_column=cols[0],source_grade=grade,source_group=TRANSCRIPTION['columns'][cols[0]]['polarClassGroup'],polar_class=pc))
    if grade=='NA':
     if required:fail('requiredHullStructuralSteelGrade','NA_CELL_MUST_NOT_STORE_REQUIRED_GRADE')
    else:
     expected=N[GRADE_NAMES[grade]]
     if required!=[expected]:fail('requiredHullStructuralSteelGrade','DIFFERS_FROM_TRANSCRIBED_TABLE8_CELL')
     ranks=m.INDEX['dependencyContracts'][req]['tableModel']['gradeFamilies'][str(family).split('#')[-1]]
     if actual is not None and (str(actual).split('#')[-1] not in ranks or ranks[str(actual).split('#')[-1]]<ranks[str(expected).split('#')[-1]]):fail('actualHullStructuralSteelGrade','GRADE_BELOW_MINIMUM_OR_INCOMPARABLE_FAMILY')
 elif req=='TRF-036':
  table={N.iceClassIaSuper:(Decimal('1.0'),Decimal('.35')),N.iceClassIa:(Decimal('.8'),Decimal('.30')),N.iceClassIb:(Decimal('.6'),Decimal('.25')),N.iceClassIc:(Decimal('.4'),Decimal('.22'))}
  parameter=one(ship,'hasIceClassDesignParameterSet');selector=one(ship,'iceClass')
  if selector is not None and selector not in table:unresolved.append(dict(property='iceClass',reason='NON_TABLE_CLASS_SOURCE_EXPECTATION_UNESTABLISHED'))
  if parameter is not None:
   hi=quantity(parameter,'levelIceThickness',U.M);h=quantity(parameter,'designIceLoadHeight',U.M)
   if selector in table:
    if hi is not None and hi!=table[selector][0]:fail('levelIceThickness','WRONG_TABLE4_1_CONSTANT')
    if h is not None and h!=table[selector][1]:fail('designIceLoadHeight','WRONG_TABLE4_1_CONSTANT')
 elif req=='I2-004':
  cases=list(g.objects(ship,N.hasUpperIceWaterlineCase))
  if not cases:fail('hasUpperIceWaterlineCase','MISSING_REPRESENTED_INPUT')
  values=[quantity(c,'waterlineCaseDisplacement',U.KiloTON_Metric) for c in cases];selected=quantity(ship,'upperIceWaterlineDisplacement',U.KiloTON_Metric)
  if values and all(v is not None for v in values) and selected is not None and selected!=max(values):fail('upperIceWaterlineDisplacement','NOT_REPRESENTED_MAXIMUM')
 elif req=='I2-005':
  points=list(g.objects(ship,N.hasBottomRegionLowerRegionBoundaryPoint))
  if not points:fail('hasBottomRegionLowerRegionBoundaryPoint','MISSING')
  for p in points:
   v=quantity(p,'shellInclinationAngle',U.DEG)
   if v is not None and v!=7:fail('shellInclinationAngle','NOT_EXACT_7_DEGREES')
 elif req=='I2-042':
  for member in g.objects(ship,N.hasStructuralMember):
   width=quantity(member,'flangeWidth',U.MilliM);web=quantity(member,'netWebThickness',U.MilliM)
   if width is not None and web is not None and width<5*web:fail('flangeWidth','BELOW_FIVE_TIMES_WEB_THICKNESS')
 elif req=='IMO-001':
  condition=one(ship,'designIceCondition')
  if condition==N.mediumFirstYearIceWithPossibleOldIceInclusions:
   category=one(ship,'shipCategory')
   if category is not None and category!=N.polarShipCategoryA:fail('shipCategory','APPLICABLE_CATEGORY_NOT_A')
 elif req=='TRF-010':
  value=one(ship,'iceClass')
  if value is not None and value not in {N[x] for x in ['iceClassIaSuper','iceClassIa','iceClassIb','iceClassIc','iceClassIi','iceClassIii']}:fail('iceClass','NOT_ONE_OF_SIX_SOURCE_CLASSES')
 elif req=='TRF-035':
  source=quantity(ship,'classificationSocietyRuleLength',U.M);result=quantity(ship,'ruleLength',U.M)
  if source is not None and result is not None and source!=result:fail('ruleLength','DIFFERS_FROM_CLASSIFICATION_RULE_LENGTH')
 elif req=='TRF-001':
  dt=one(ship,'constructionContractDate');edition=one(ship,'applicableIceClassRegulationEdition',required=False)
  ps=set(g.objects(ship,N.applicableIceClassRegulatoryProvision))
  for p in [N.iceClassSection1Point8Provision2021,N.iceClassDraughtChapter2Provision2021]:
   if p not in ps:fail('applicableIceClassRegulatoryProvision','MISSING_UNIVERSAL_PROVISION:'+str(p))
  if dt is not None:
   if not isinstance(dt,Literal) or dt.datatype!=XSD.date:fail('constructionContractDate','NOT_CANONICAL_DATE')
   elif date.fromisoformat(str(dt))>=date(2021,7,5) and edition!=N.iceClassRegulationEdition2021:fail('applicableIceClassRegulationEdition','WRONG_OR_MISSING_POSTCUTOFF_EDITION')
 elif req=='TRF-050':
  frames=objects_of_class('frame')
  if not frames:unresolved.append(dict(reason='FRAME_IDENTITY_UNRESOLVED'))
  for frame in frames:
   record=one(frame,'frameAttachment')
   if record is None:continue
   weld=one(record,'frameShellWeldType');crossing=one(record,'shellPlateButtCrossing');scallop=one(record,'scallopingPresent')
   if weld is not None and weld!=N.doubleContinuousWeld:fail('frameShellWeldType','NOT_DOUBLE_CONTINUOUS_WELD')
   if crossing is not None and (not isinstance(crossing,Literal) or crossing.datatype!=XSD.boolean):fail('shellPlateButtCrossing','NOT_BOOLEAN')
   if scallop is not None and (not isinstance(scallop,Literal) or scallop.datatype!=XSD.boolean):fail('scallopingPresent','NOT_BOOLEAN')
   if crossing==Literal(False) and scallop==Literal(True):fail('scallopingPresent','SCALLOPING_AWAY_FROM_BUTT_CROSSING')
 elif req=='TRF-058':
  frames=objects_of_class('webFrame')
  if not frames:unresolved.append(dict(reason='WEB_FRAME_IDENTITY_UNRESOLVED'))
  for frame in frames:
   flags=list(g.objects(frame,N.supportedStringerOutsideIceBelt))
   if not flags:unresolved.append(dict(property='supportedStringerOutsideIceBelt',reason='APPLICABILITY_NOT_EXPLICIT_AND_NO_APPROVED_DERIVATION'));continue
   if flags==[Literal(False)]:continue
   if flags!=[Literal(True)]:unresolved.append(dict(property='supportedStringerOutsideIceBelt',reason='APPLICABILITY_LITERAL_UNRESOLVED'));continue
   force=quantity(frame,'iceLoadForce',U.KiloN);height=quantity(frame,'stringerOutsideIceBeltHeight',U.M);span=quantity(frame,'stringerSpan',U.M);actual=quantity(frame,'adjustedIceLoadForce',U.KiloN)
   if None not in [force,height,span,actual]:
    if span==0:unresolved.append(dict(property='stringerSpan',reason='ZERO_SPAN_INPUT'))
    elif actual!=force*(1-height/span):fail('adjustedIceLoadForce','NOT_FORCE_TIMES_ONE_MINUS_HS_OVER_LS')
 else:raise ValueError(req)
 return dict(conforms=None if unresolved else not defects,defects=defects,unresolved=unresolved,witness=witness,source_law=PLANS[req]['law'])


def review():
 screens=m.read(D/'screened_cases.json');out=[]
 for old in screens:
  c=copy.deepcopy(old);q=c['requirement_id'];cid=c['case_id'];g=Graph().parse(c['fixture']);c['schema']=m.schema_inventory(g,q);c['freeze_verified']=False;c['gold_expectation_verified']=False;c['freeze_blockers']=[];c['review_status']='SCREENED_ONLY_NOT_CERTIFIED'
  if c['source_evidence_blocker']:c['freeze_blockers'].append(dict(code=c['source_evidence_blocker'],detail='Frozen source expectation requires source reconciliation.'))
  if c['schema']['unresolved_binding_properties']:c['freeze_blockers'].append(dict(code='EXPLICIT_SCHEMA_BINDINGS_NOT_FULLY_REVIEWED',properties=c['schema']['unresolved_binding_properties'],detail='TermOwners does not bind every indexed regulatory property. Missing ownership is not filled from domain or fallback requiredOwner.'))
  c['freeze_blockers'].extend(c['source_scope_issues'])
  if q not in PLANS:
   c['freeze_blockers'].append(dict(code='SOURCE_ORACLE_SCOPE_AND_BRANCHES_NOT_AUDITED',detail=f'{q} {c["source_clause"]}: authoring oracle agrees with the supplied {c["expected"]} label but its full source/schema coverage has not been certified in this assessment.'))
  else:
   c['independent_source_review']=fresh_oracle(g,q)
   result=c['independent_source_review']['conforms']
   if result is None:c['freeze_blockers'].append(dict(code='INDEPENDENT_APPLICABILITY_OR_BINDING_UNRESOLVED',evidence=c['independent_source_review']['unresolved']))
   elif result!=(c['expected']=='PASS'):c['freeze_blockers'].append(dict(code='SOURCE_EXPECTATION_DISAGREEMENT_REQUIRES_ADJUDICATION',expected=c['expected'],independent_conforms=result,evidence=c['independent_source_review']['defects']))
   if c['expected']=='PASS' and c['schema']['issues']:c['freeze_blockers'].append(dict(code='POSITIVE_SCHEMA_ISSUES_REQUIRING_REVIEW',evidence=c['schema']['issues']))
   if result is not None and result==(c['expected']=='PASS') and not c['freeze_blockers']:
    c['gold_expectation_verified']=True
   if c['expected']=='FAIL':
    repair=c.get('repair',{});p=repair.get('path')
    if not p:c['freeze_blockers'].append(dict(code='NO_EXISTING_INTENDED_ONLY_COUNTERFACTUAL',detail=repair.get('method')))
    else:
     good=Graph().parse(p);check=fresh_oracle(good,q);schema=m.schema_inventory(good,q);roots=m.prepare.semantic_roots(g,good)
     original_props={str(p).removeprefix(str(N)) for s,p in roots};defect_props={x['property'] for x in c['independent_source_review']['defects']}
     c['independent_repair_review']=dict(path=p,sha256=m.sha(p),source_oracle=check,schema=schema,semantic_roots=[[str(s),str(p)] for s,p in roots],one_intended_property_changed=len(original_props)==1,intended_defect_corresponds_to_operation=bool(defect_props) and defect_props<=original_props,operation_evidence='Existing reviewed counterfactual only; no repair selected from generated shape behavior.')
     if check['conforms'] is not True or schema['issues'] or schema['unresolved_binding_properties']:c['freeze_blockers'].append(dict(code='REPAIR_NOT_SOURCE_SCHEMA_CERTIFIED',evidence=c['independent_repair_review']))
     if len(original_props)!=1 or not defect_props or not defect_props<=original_props:c['freeze_blockers'].append(dict(code='INTENDED_ONLY_REPAIR_CORRESPONDENCE_NOT_ESTABLISHED',properties=sorted(original_props),defect_properties=sorted(defect_props)))
   if not c['freeze_blockers']:c['freeze_verified']=True;c['review_status']='SOURCE_AND_SCHEMA_VERIFIED_POSITIVE' if c['expected']=='PASS' else 'SOURCE_AND_SCHEMA_VERIFIED_NEGATIVE_WITH_REPAIR'
  if c['historical_case_state']=='BLOCKED' and c['existing_blockers']:c['historical_pending_issues']=c['existing_blockers']
  if c['gold_expectation_verified'] and not c['freeze_verified']:c['review_status']='SOURCE_GOLD_VERIFIED_REPAIR_PENDING'
  elif not c['freeze_verified'] and 'independent_source_review' in c:c['review_status']='SOURCE_REVIEW_UNRESOLVED'
  elif not c['freeze_verified'] and c['source_scope_issues']:c['review_status']='SCREENED_WITH_KNOWN_SOURCE_SCOPE_BLOCKER'
  if q in PLANS:c['verification_scope']=PLANS[q]['scope']
  if q=='I2-048':c['verification_scope']='General source-transcribed Table-8 lookup/grade-rank model, excluding discretionary single-strake footnote-2 allowance. NA/PASS is faithful lookup representation, not fitness-for-service approval.'
  out.append(c)
 m.save('reviewed_cases.json',out)
 plans={}
 for q,plan in PLANS.items():
  cases=[c for c in out if c['requirement_id']==q];ids={c['case_id'] for c in cases};p=copy.deepcopy(plan)
  for branch,cids in p['branches'].items():
   assert set(cids)<=ids,(q,branch,cids)
  if q=='I2-048':p['branches']['source_cell_positive_matrix']=[c['case_id'] for c in cases if c['expected']=='PASS']
  p['case_ids']=sorted(ids);p['all_cases_source_schema_verified']=all(c['freeze_verified'] for c in cases)
  p['verified_positive_case_ids']=[c['case_id'] for c in cases if c['expected']=='PASS' and c['freeze_verified']]
  p['verified_negative_case_ids']=[c['case_id'] for c in cases if c['expected']=='FAIL' and c['freeze_verified']]
  p['source_text']=cases[0]['source_text'];p['source_evidence']=cases[0]['source_evidence'];p['explicit_term_owners']=m.INDEX['termOwners'].get(q,{})
  p['eligible_to_freeze_as_represented_core']=p['status']=='DEFENSIBLE_REPRESENTED_CORE' and p['all_cases_source_schema_verified']
  plans[q]=p
 m.save('reviewed_branch_specifications.json',plans)
 print('Freshly certified cases',Counter((c['requirement_id'],c['expected'],c['freeze_verified']) for c in out if c['requirement_id'] in PLANS),flush=True)
 print('Core approvals',[(q,p['eligible_to_freeze_as_represented_core']) for q,p in plans.items()],flush=True)

if __name__=='__main__':review()
