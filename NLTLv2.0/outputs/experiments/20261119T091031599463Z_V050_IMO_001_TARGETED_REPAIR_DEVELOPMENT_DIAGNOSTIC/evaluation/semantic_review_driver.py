"""Post-completion, source/constraint-based attribution. No model or repair imports."""
from pathlib import Path
from collections import deque,Counter
from decimal import Decimal
import json,re,shutil
from rdflib import Graph,URIRef,RDF,Literal,XSD
from rdflib.namespace import SH
from rdflib.collection import Collection
from nltlv2.core import Project,load,write,offline_network_guard
from nltlv2.schema import Schema,N,Q,U
STATE=Path('/private/tmp/imo_001_v050_targeted_state_20261119.json')
def route(data,root,focus):
 if root==focus:return []
 queue=deque([(root,[])]);seen={root}
 while queue:
  node,path=queue.popleft()
  for pred,obj in data.predicate_objects(node):
   if pred==RDF.type or not isinstance(obj,URIRef) or obj in seen:continue
   step=path+[str(pred)]
   if obj==focus:return step
   if len(step)<5:seen.add(obj);queue.append((obj,step))
 return None

def run():
 state=load(STATE);assert state['status']=='DIAGNOSTIC_FINISHED';group=Path(state['group']);out=group/'evaluation';schema=Schema(Project(group/'snapshot'));rows=load(out/'raw_results.json');cases=load(out/'reviewed_selection.json')['cases'];spec={c['case_id']:c for c in cases};reviews=[]
 with offline_network_guard():
  for row in rows:
   row['requirement_id']='IMO-001';row['method']='SEEDED_DIAGNOSTIC'
   for detail in row['violation_details']:detail['result_node']=detail['node']
  for row in rows:
   if row['expected']!='FAIL':continue
   status=row['strict_provisional']
   if status!='PENDING_SEMANTIC_REVIEW':row['strict']=status;continue
   rid=row['requirement_id'];case=spec[row['case_id']];defect=case['source_review']['independent_source_review']['defects'];assert len(defect)==1;prop=defect[0]['property'];reason=defect[0]['reason'];shape=Graph().parse(group/'diagnostic'/f"candidate_{row['version']:02d}.ttl");data=Graph().parse(out/'inputs'/Path(case['fixture']).name);ship=next(data.subjects(RDF.type,N.ship));allowed=schema.allowed_paths(rid)[1][str(N[prop])];queries=list(map(str,shape.objects(None,SH.select)));details=row['violation_details'];byid={d['result_node']:d for d in details};meanings=[];resolved=True
   # Inspect leaf constraints; wrappers must link only to the same reviewed leaves.
   for detail in details:
    if detail['details']:
     if detail['component']!=str(SH.NodeConstraintComponent) or any(child not in byid for child in detail['details']):resolved=False
     continue
    path=route(data,ship,URIRef(detail['focus']));fullpath=None if path is None else path+([detail['path']] if detail['path'] else []);component=detail['component'];meaning=None;params={}
    if component==str(SH.MinCountConstraintComponent):
     if fullpath in [list(x) for x in allowed] and [str(SH.minCount),Literal(1).n3()] in detail['source_triples'] and not list(data.objects(URIRef(detail['focus']),URIRef(detail['path']))):meaning='INTENDED_MISSING_REQUIRED_INPUT';params['minCount']=1
    elif component in [str(SH.MinInclusiveConstraintComponent),str(SH.MaxInclusiveConstraintComponent)] and rid=='I2-005' and reason=='NOT_EXACT_7_DEGREES':
     values=list(data.objects(URIRef(detail['focus']),Q.numericValue));predicate=SH.minInclusive if component==str(SH.MinInclusiveConstraintComponent) else SH.maxInclusive
     if fullpath in [list(x)+[str(Q.numericValue)] for x in allowed] and values and all(v.datatype==XSD.decimal and (Decimal(str(v))<7 if predicate==SH.minInclusive else Decimal(str(v))>7) for v in values) and [str(predicate),Literal('7',datatype=XSD.decimal).n3()] in detail['source_triples']:
      meaning='INTENDED_NUMERIC_ANGLE_NOT_SEVEN';params=dict(bound_predicate=str(predicate),source_constant=7,observed_values=[v.n3() for v in values],reason='Exact source-backed inclusive bounds test numeric equality; the applicable side fails on the intended unequal angle.')
    elif component==str(SH.HasValueConstraintComponent):
     if reason=='WRONG_CANONICAL_UNIT':
      expected=schema.terms[str(N[prop])]['unitIri'];actual=list(map(str,data.objects(URIRef(detail['focus']),Q.unit)))
      if fullpath in [list(x)+[str(Q.unit)] for x in allowed] and expected not in actual and [str(SH.hasValue),URIRef(expected).n3()] in detail['source_triples']:meaning='INTENDED_WRONG_CANONICAL_UNIT';params=dict(expected_unit=expected,observed_units=actual)
     elif rid=='I2-005' and reason=='NOT_EXACT_7_DEGREES':
      values=list(data.objects(URIRef(detail['focus']),Q.numericValue));expected_literal=Literal('7',datatype=XSD.decimal)
      if fullpath in [list(x)+[str(Q.numericValue)] for x in allowed] and values and all(Decimal(str(v))!=7 for v in values) and [str(SH.hasValue),expected_literal.n3()] in detail['source_triples']:meaning='INTENDED_NUMERIC_ANGLE_NOT_SEVEN';params=dict(expected_value=7,observed_values=[v.n3() for v in values],limitation='Term equality is overrestrictive on other lexical forms; this particular defect changes the numeric value and its certified repair fully passes.')
    elif component==str(SH.InConstraintComponent) and rid=='TRF-010':
     expected={URIRef(m['iri']) for m in schema.enumeration_obligations[rid][0]['members']};members=[set(Collection(shape,head)) for ps in shape.subjects(SH.path,N.iceClass) for head in shape.objects(ps,SH['in'])];value=URIRef(detail['value'])
     if fullpath==[str(N.iceClass)] and expected in members and value in data.objects(ship,N.iceClass) and value not in expected:meaning='INTENDED_UNLISTED_ICE_CLASS';params=dict(expected_IRIs=sorted(map(str,expected)),actual_value=str(value))
    elif component==str(SH.SPARQLConstraintComponent) and len(queries)==1:
     query=queries[0];compact=re.sub(r'\s+','',query)
     if rid=='I2-004' and prop=='upperIceWaterlineDisplacement' and reason=='NOT_REPRESENTED_MAXIMUM' and URIRef(detail['focus'])==ship:
      if row['method']=='NLTL' and all(s in compact for s in ['||','NOTEXISTS','EXISTS','?greaterValue>?resultValue','?caseValue=?resultValue','waterlineCaseDisplacement','upperIceWaterlineDisplacement']):meaning='INTENDED_SELECTED_DISPLACEMENT_NOT_MAXIMUM';params=dict(query=query,complete_paths=['ship/upperIceWaterlineDisplacement/qudt:numericValue','ship/hasUpperIceWaterlineCase/waterlineCaseDisplacement/qudt:numericValue'],reason='A case above the selected value OR no case equal to the selected value describes selected != maximum on these complete inputs. Bound outer result and applicable target inspected.')
     elif rid=='I2-005' and reason=='NOT_EXACT_7_DEGREES':
      values=list(data.objects(URIRef(detail['focus']),Q.numericValue));units=list(data.objects(URIRef(detail['focus']),Q.unit))
      if path in [list(x) for x in allowed] and values and all(Decimal(str(v))!=7 for v in values) and units==[U.DEG] and '?value!=' in compact and '"7"^^xsd:decimal' in compact and 'unit:DEG' in query:meaning='INTENDED_NUMERIC_ANGLE_NOT_SEVEN';params=dict(query=query,observed_values=[v.n3() for v in values],applicable_branch='Numeric inequality branch. Canonical DEG unit branch is satisfied, so no unrelated unit defect.')
     elif rid=='I2-005' and reason=='WRONG_CANONICAL_UNIT':
      values=list(data.objects(URIRef(detail['focus']),Q.numericValue));units=list(data.objects(URIRef(detail['focus']),Q.unit))
      if path in [list(x) for x in allowed] and values and all(v.datatype==XSD.decimal and Decimal(str(v))==7 for v in values) and len(units)==1 and U.DEG not in units and '?unitValue!=unit:DEG' in compact:
       meaning='INTENDED_WRONG_CANONICAL_UNIT';params=dict(query=query,observed_units=list(map(str,units)),expected_unit=str(U.DEG),reason='Only the wrong-unit UNION branch applies; numeric inequality is false for the correct numeric angle.')
     elif rid=='IMO-001' and prop=='shipCategory' and URIRef(detail['focus'])==ship:
      condition=list(data.objects(ship,N.designIceCondition));category=list(data.objects(ship,N.shipCategory))
      if condition==[N.mediumFirstYearIceWithPossibleOldIceInclusions] and N.polarShipCategoryA not in category and all(s in query for s in ['mediumFirstYearIceWithPossibleOldIceInclusions','polarShipCategoryA','shipCategory','NOT EXISTS']):meaning='INTENDED_APPLICABLE_CATEGORY_MISSING_OR_NOT_A';params=dict(query=query,applicable_selector=str(condition[0]),categories=list(map(str,category)),reason='Actual controlled selector activates the Category A obligation. Missing A / other category query branches describe the same intended category defect on this singleton/missing-value fixture; the full intended-only repair passes. No multiplicity inference.')
     elif rid=='TRF-035' and prop=='ruleLength' and reason=='DIFFERS_FROM_CLASSIFICATION_RULE_LENGTH' and URIRef(detail['focus'])==ship:
      if all(s in query for s in ['classificationSocietyRuleLength','ruleLength','numericValue','?resultValue != ?operandValue']):meaning='INTENDED_NUMERIC_LENGTH_INEQUALITY';params=dict(query=query,complete_paths=['ship/ruleLength/qudt:numericValue','ship/classificationSocietyRuleLength/qudt:numericValue'],reason='Both scalar operands are bound on the explicit paths, and numeric inequality reports the source equality defect.')
    if meaning is None:resolved=False
    meanings.append(dict(result_node=detail['result_node'],meaning=meaning or 'UNRESOLVED',focus=detail['focus'],complete_path=fullpath,component=component,parameters=params,source_triples=detail['source_triples']))
   status='VERIFIED_INTENDED_DETECTION' if resolved and meanings and row['repaired_verdict']['conforms'] is True else 'UNRESOLVED_ATTRIBUTION'
   row['strict']=status;row['attribution_review']=dict(method='Source/explicit-path/constraint-query semantics and nested detail with certified passing counterfactual; no message or blank-node-ID matching',leaves=meanings,wrapper_count=sum(bool(d['details']) for d in details),wrapper_interpretation='Parent sh:node wrappers describe the same reviewed descendant failures; no independent unrelated leaf was omitted.')
   reviews.append(dict(requirement_id=rid,method=row['method'],version=row['version'],candidate_sha256=row['candidate_sha256'],case_id=row['case_id'],classification=status,intended_defect=defect,source=case['source_review']['independent_source_review'],contract_evidence=schema.context(rid)['contract'],review=row['attribution_review'],counterfactual_sha256=case['counterfactual_sha256'],reports_path=row['reports_path']))
  shutil.copyfile(__file__,out/'semantic_review_driver.py');write(out/'semantic_adjudications.json',reviews);write(out/'adjudicated_candidate_results.json',rows)
  print('Reviewed',len(reviews),'pending rows; unresolved',sum(r.get('strict')=='UNRESOLVED_ATTRIBUTION' for r in rows))
if __name__=='__main__':run()
