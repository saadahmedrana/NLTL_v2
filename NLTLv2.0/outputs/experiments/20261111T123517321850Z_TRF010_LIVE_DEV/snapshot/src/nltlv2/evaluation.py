"""External evaluation only. Nothing in this module is imported by generation/repair."""
from __future__ import annotations
from decimal import Decimal
import json,collections
from rdflib import Graph,Literal,RDF,XSD,URIRef
from rdflib.namespace import SH
from pyshacl import validate
from .core import load,write,digest
from .schema import N,Q,U,Schema
from .sparql_extensions import register_math_functions

def oracle(g,rid):
 """Source-authored oracle for the six represented development requirements only."""
 issues=[];unresolved=[];ships=list(g.subjects(RDF.type,N.ship))
 if len(ships)!=1:return dict(conforms=None,issues=[],unresolved=['SHIP_IDENTITY_NOT_UNIQUE'])
 ship=ships[0]
 def one(s,p):
  vs=list(g.objects(s,N[p]))
  if not vs:issues.append(p);return None
  if len(vs)!=1:unresolved.append('MULTIVALUED_'+p);return None
  return vs[0]
 def quantity(s,p,unit):
  node=one(s,p)
  if node is None:return None
  ns=list(g.objects(node,Q.numericValue));us=list(g.objects(node,Q.unit))
  if len(ns)!=1 or not isinstance(ns[0],Literal) or ns[0].datatype!=XSD.decimal or us!=[unit]:issues.append(p);return None
  try:return Decimal(str(ns[0]))
  except Exception:issues.append(p);return None
 if rid=='I2-004':
  cs=list(g.objects(ship,N.hasUpperIceWaterlineCase))
  if not cs:issues.append('hasUpperIceWaterlineCase')
  vals=[quantity(c,'waterlineCaseDisplacement',U.KiloTON_Metric) for c in cs];selected=quantity(ship,'upperIceWaterlineDisplacement',U.KiloTON_Metric)
  if vals and None not in vals and selected is not None and selected!=max(vals):issues.append('upperIceWaterlineDisplacement')
 elif rid=='I2-005':
  ps=list(g.objects(ship,N.hasBottomRegionLowerRegionBoundaryPoint))
  if not ps:issues.append('hasBottomRegionLowerRegionBoundaryPoint')
  for p in ps:
   v=quantity(p,'shellInclinationAngle',U.DEG)
   if v is not None and v!=7:issues.append('shellInclinationAngle')
 elif rid=='I2-042':
  for m in g.objects(ship,N.hasStructuralMember):
   w=quantity(m,'flangeWidth',U.MilliM);t=quantity(m,'netWebThickness',U.MilliM)
   if w is not None and t is not None and w<5*t:issues.append('flangeWidth')
 elif rid=='IMO-001':
  cond=one(ship,'designIceCondition')
  if cond==N.mediumFirstYearIceWithPossibleOldIceInclusions:
   category=one(ship,'shipCategory')
   if category is not None and category!=N.polarShipCategoryA:issues.append('shipCategory')
 elif rid=='TRF-010':
  v=one(ship,'iceClass')
  if v is not None and v not in {N[x] for x in ['iceClassIaSuper','iceClassIa','iceClassIb','iceClassIc','iceClassIi','iceClassIii']}:issues.append('iceClass')
 elif rid=='TRF-035':
  a=quantity(ship,'classificationSocietyRuleLength',U.M);b=quantity(ship,'ruleLength',U.M)
  if a is not None and b is not None and a!=b:issues.append('ruleLength')
 else:return dict(conforms=None,issues=[],unresolved=['NO_CERTIFIED_SOURCE_ORACLE'])
 return dict(conforms=None if unresolved else not issues,issues=sorted(set(issues)),unresolved=unresolved)

def validate_pair_graph(data,shape,schema):
 register_math_functions()
 try:
  conforms,report,text=validate(data,shacl_graph=shape,ont_graph=schema.graph,inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False)
  if not isinstance(report,Graph):return dict(conforms=None,error=str(report)),None
  violations=[]
  for r in report.subjects(RDF.type,SH.ValidationResult):
   source=report.value(r,SH.sourceShape)
   violations.append(dict(focus=str(report.value(r,SH.focusNode)),path=str(report.value(r,SH.resultPath) or ''),component=str(report.value(r,SH.sourceConstraintComponent)),source_shape=str(source),messages=list(map(str,report.objects(r,SH.resultMessage)))))
  return dict(conforms=bool(conforms),violations=violations),report
 except Exception as e:return dict(conforms=None,error=type(e).__name__+': '+str(e)),None

def strict_status(negative,repaired,intended,unrelated,*,certified=True,original_no_verdict=False,attribution_resolved=True):
 if original_no_verdict or negative is None or repaired is None:return 'NO_VERDICT'
 if not certified:return 'UNRESOLVED_ATTRIBUTION'
 if negative is True:return 'MISSED_INTENDED_DEFECT'
 if unrelated or repaired is False:return 'UNRELATED_OR_ADDITIONAL_FAILURE'
 if not attribution_resolved:return 'UNRESOLVED_ATTRIBUTION'
 if intended:return 'VERIFIED_INTENDED_DETECTION'
 return 'UNRESOLVED_ATTRIBUTION'

def reference_queries(rid):
 # Explicit source-authored development controls, never claimed generated outputs.
 def missing_qty(owner,p,u):return f'FILTER NOT EXISTS {{ {owner} n:{p} ?q . ?q q:numericValue ?v ; q:unit u:{u} . FILTER(datatype(?v)=xsd:decimal) }}'
 if rid=='I2-004':return [('hasUpperIceWaterlineCase','FILTER NOT EXISTS { $this n:hasUpperIceWaterlineCase ?c }'),('waterlineCaseDisplacement',' $this n:hasUpperIceWaterlineCase ?c . '+missing_qty('?c','waterlineCaseDisplacement','KiloTON_Metric')),('upperIceWaterlineDisplacement',missing_qty('$this','upperIceWaterlineDisplacement','KiloTON_Metric')),('upperIceWaterlineDisplacement','$this n:upperIceWaterlineDisplacement/q:numericValue ?s . FILTER( EXISTS { $this n:hasUpperIceWaterlineCase/n:waterlineCaseDisplacement/q:numericValue ?v . FILTER(?v > ?s) } || NOT EXISTS { $this n:hasUpperIceWaterlineCase/n:waterlineCaseDisplacement/q:numericValue ?v . FILTER(?v = ?s) })')]
 if rid=='I2-005':return [('hasBottomRegionLowerRegionBoundaryPoint','FILTER NOT EXISTS { $this n:hasBottomRegionLowerRegionBoundaryPoint ?p }'),('shellInclinationAngle','$this n:hasBottomRegionLowerRegionBoundaryPoint ?p . '+missing_qty('?p','shellInclinationAngle','DEG')),('shellInclinationAngle','$this n:hasBottomRegionLowerRegionBoundaryPoint/n:shellInclinationAngle/q:numericValue ?v . FILTER(?v != 7)')]
 if rid=='I2-042':return [('flangeWidth','$this n:hasStructuralMember ?m . '+missing_qty('?m','flangeWidth','MilliM')),('netWebThickness','$this n:hasStructuralMember ?m . '+missing_qty('?m','netWebThickness','MilliM')),('flangeWidth','$this n:hasStructuralMember ?m . ?m n:flangeWidth/q:numericValue ?w ; n:netWebThickness/q:numericValue ?t . FILTER(?w < 5*?t)')]
 if rid=='IMO-001':return [('designIceCondition','FILTER NOT EXISTS { $this n:designIceCondition ?d }'),('shipCategory','$this n:designIceCondition n:mediumFirstYearIceWithPossibleOldIceInclusions . FILTER NOT EXISTS { $this n:shipCategory n:polarShipCategoryA }')]
 if rid=='TRF-010':return [('iceClass','FILTER NOT EXISTS { $this n:iceClass ?v . FILTER(?v IN (n:iceClassIaSuper,n:iceClassIa,n:iceClassIb,n:iceClassIc,n:iceClassIi,n:iceClassIii)) }')]
 if rid=='TRF-035':return [('classificationSocietyRuleLength',missing_qty('$this','classificationSocietyRuleLength','M')),('ruleLength',missing_qty('$this','ruleLength','M')),('ruleLength','$this n:classificationSocietyRuleLength/q:numericValue ?a ; n:ruleLength/q:numericValue ?b . FILTER(?a != ?b)')]
 raise ValueError(rid)

def reference_shape(rid):
 g=Graph();semantics={};prefix='PREFIX n: <'+str(N)+'> PREFIX q: <'+str(Q)+'> PREFIX u: <'+str(U)+'> PREFIX xsd: <'+str(XSD)+'> '
 for i,(prop,body) in enumerate(reference_queries(rid)):
  s=URIRef(f'urn:nltlv2:development-reference:{rid}:{i}');query=URIRef(str(s)+':query');g.add((s,RDF.type,SH.NodeShape));g.add((s,SH.targetClass,N.ship));g.add((s,SH.sparql,query));g.add((query,SH.select,Literal(prefix+'SELECT $this WHERE { '+body+' }')));g.add((query,SH.message,Literal('Source-authored development control: '+prop)));semantics[str(s)]=prop
 return g,semantics

def core_regression(project,out):
 schema=Schema(project);selection=load(project.path('evaluation/selections/regression_core.json'));rows=[]
 for c in selection['cases']:
  cid=c['case_id'];rid=c['requirement_id'];dest=out/cid;dest.mkdir();data=Graph().parse(project.path(c['fixture']));check=oracle(data,rid)
  if check['conforms']!=(c['expected']=='PASS'):raise AssertionError((cid,'INDEPENDENT_ORACLE_DISAGREES',check))
  shapes,semantics=reference_shape(rid);shapes.serialize(dest/'source_authored_reference.ttl',format='turtle');neg,report=validate_pair_graph(data,shapes,schema)
  if report is not None:report.serialize(dest/'original_report.ttl',format='turtle')
  if neg['conforms']!=(c['expected']=='PASS'):raise AssertionError((cid,neg))
  row=dict(case_id=cid,requirement_id=rid,expected=c['expected'],independent_oracle=check,verdict=neg,ordinary_agreement=True,arm='SOURCE_AUTHORED_DEVELOPMENT_REFERENCE_NOT_GENERATED')
  if c['expected']=='FAIL':
   repaired_data=Graph().parse(project.path(c['counterfactual']));oc=oracle(repaired_data,rid)
   if oc['conforms'] is not True:raise AssertionError((cid,'INVALID_REPAIR',oc))
   rep,rr=validate_pair_graph(repaired_data,shapes,schema)
   if rr is not None:rr.serialize(dest/'repaired_report.ttl',format='turtle')
   unrelated=[v for v in neg['violations'] if semantics.get(v['source_shape']) not in check['issues']]
   row.update(repaired_oracle=oc,repaired_verdict=rep,strict=strict_status(neg['conforms'],rep['conforms'],bool(neg['violations']),bool(unrelated)),attribution_basis='Source-authored reference query semantics mapped independently to oracle defect properties, never message text.')
   if row['strict']!='VERIFIED_INTENDED_DETECTION':raise AssertionError(row)
  rows.append(row)
 result=dict(scope='Development reference controls only, not automatic generation/repair performance',requirements=6,positive=17,negative=20,positive_acceptance=17,strict_reference_detection=20,rows=rows);write(out/'external_core_regression.json',result);return result

def check_exclusions(by_workflow):
 sets={workflow:set(ids) for workflow,ids in by_workflow.items()}
 if sets and any(v!=next(iter(sets.values())) for v in sets.values()):raise ValueError('EXCLUSIONS_DIFFER_ACROSS_WORKFLOWS')
 return sorted(next(iter(sets.values()))) if sets else []

def evaluate(project,shape_manifest,out):
 """Evaluate unchanged submitted shapes; unseen violation semantics remain unresolved."""
 schema=Schema(project);core=load(project.path('evaluation/selections/regression_core.json'));manifest=load(project.path(shape_manifest))
 if set(manifest['workflows'])!={'NLTL','Single-shot'}:raise ValueError('Exactly the same two workflows required')
 exclusions=check_exclusions(manifest.get('excluded_case_ids',{'NLTL':[],'Single-shot':[]}))
 if exclusions:raise ValueError('The certified 37-case core has no established invalid-test exclusions. Supply a separately reviewed versioned selection to change it.')
 rows=[]
 for wf,shapes in manifest['workflows'].items():
  for c in core['cases']:
   entry=shapes.get(c['requirement_id']);dest=out/wf/c['case_id'];dest.mkdir(parents=True);g=Graph().parse(project.path(c['fixture']));oc=oracle(g,c['requirement_id'])
   if not entry or entry.get('original_no_verdict'):
    rows.append(dict(workflow=wf,case_id=c['case_id'],requirement_id=c['requirement_id'],expected=c['expected'],conforms=None,ordinary_agreement=None,strict='NO_VERDICT' if c['expected']=='FAIL' else None));continue
   shape=Graph().parse(project.path(entry['shape']));verdict,report=validate_pair_graph(g,shape,schema)
   if report is not None:report.serialize(dest/'negative_or_positive_report.ttl',format='turtle')
   row=dict(workflow=wf,case_id=c['case_id'],requirement_id=c['requirement_id'],expected=c['expected'],verdict=verdict,conforms=verdict['conforms'],ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'))
   if c['expected']=='FAIL':
    repair=Graph().parse(project.path(c['counterfactual']));repaired_oracle=oracle(repair,c['requirement_id']);rv,rr=validate_pair_graph(repair,shape,schema)
    if rr is not None:rr.serialize(dest/'repaired_report.ttl',format='turtle')
    # Accept exact pre-reviewed source-authored query bodies only. Unknown wrappers/queries are unresolved.
    refs,semantics=reference_shape(c['requirement_id']);reviewed_queries={str(refs.value(q,SH.select)):semantics[str(s)] for s,q in refs.subject_objects(SH.sparql)}
    meanings=[]
    for v in verdict.get('violations',[]):
     source=URIRef(v['source_shape']);queries=list(shape.objects(source,SH.sparql));meaning=[reviewed_queries.get(str(shape.value(q,SH.select))) for q in queries]
     meanings.append(meaning[0] if len(meaning)==1 else None)
    resolved=all(x is not None for x in meanings)
    row.update(repaired_verdict=rv,independent_oracle=oc,repaired_oracle=repaired_oracle,strict=strict_status(verdict['conforms'],rv['conforms'],bool(meanings),any(x not in oc['issues'] for x in meanings if x is not None),certified=repaired_oracle['conforms'] is True,attribution_resolved=resolved),attribution='Reviewed query-body correspondence only; unreviewed SHACL/wrapper semantics remain unresolved.')
   rows.append(row)
 summary={}
 for wf in manifest['workflows']:
  rs=[r for r in rows if r['workflow']==wf];negative=[r for r in rs if r['expected']=='FAIL'];positive=[r for r in rs if r['expected']=='PASS']
  summary[wf]=dict(total_denominator=len(rs),ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rs),executable=sum(r['conforms'] is not None for r in rs),no_verdict=sum(r['conforms'] is None for r in rs),positive_denominator=len(positive),positive_acceptance=sum(r['conforms'] is True for r in positive),negative_denominator=len(negative),strict_counts=dict(collections.Counter(r['strict'] for r in negative)))
 common=[c['case_id'] for c in core['cases'] if c['expected']=='FAIL' and all(next(r for r in rows if r['case_id']==c['case_id'] and r['workflow']==w)['strict'] not in ['UNRESOLVED_ATTRIBUTION'] for w in manifest['workflows'])]
 result=dict(scope='37-case six-requirement development core only; unchanged shapes; not full-benchmark accuracy',summaries=summary,common_classified_negative_ids=common,common_negative_denominator=len(common),rows=rows,exclusions=exclusions);write(out/'independent_evaluation.json',result);return result
