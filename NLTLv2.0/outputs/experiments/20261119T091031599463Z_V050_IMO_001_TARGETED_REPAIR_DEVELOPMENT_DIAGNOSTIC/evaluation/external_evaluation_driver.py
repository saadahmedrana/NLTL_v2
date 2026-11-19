"""External evaluation only after TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC closes.
No generation/repair transport imports or feedback to the completed diagnostic.
"""
from pathlib import Path
import collections,json,hashlib,shutil,time
from rdflib import Graph,URIRef,RDF
from rdflib.namespace import SH
from nltlv2.core import Project,load,write,offline_network_guard,digest
from nltlv2.schema import Schema
from nltlv2.evaluation import oracle,validate_pair_graph
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/imo_001_v050_targeted_state_20261119.json');LABEL='TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def run():
 state=load(STATE);assert state['status']=='DIAGNOSTIC_FINISHED';group=Path(state['group']);out=group/'evaluation';out.mkdir(exist_ok=False);shutil.copyfile(__file__,out/'external_evaluation_driver.py');cases=[c for c in load(ROOT/'evaluation/selections/five_requirement_development.json')['cases'] if c['requirement_id']=='IMO-001'];assert cases and all(c.get('counterfactual') for c in cases if c['expected']=='FAIL')
 write(out/'reviewed_selection.json',dict(label=LABEL,cases=cases,exclusions=[],positive=sum(c['expected']=='PASS' for c in cases),negative=sum(c['expected']=='FAIL' for c in cases),repaired=sum(c['expected']=='FAIL' for c in cases),evaluation_after_diagnostic=True))
 inputs=out/'inputs';inputs.mkdir()
 for c in cases:
  for k in ['fixture','counterfactual']:
   if c.get(k):assert sha(ROOT/c[k])==c[k+'_sha256'];shutil.copyfile(ROOT/c[k],inputs/Path(c[k]).name)
 schema=Schema(Project(group/'snapshot'));rows=[];index=[];started=time.monotonic()
 write(out/'validation_options.json',dict(label=LABEL,version='0.5.0',inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False,schema_sha256=sha(group/'snapshot/schema/Schema_for_NLTL.ttl'),transformed_shapes=False,feedback_to_repair=False))
 with offline_network_guard():
  for file in sorted((group/'diagnostic').glob('candidate_*.ttl')):
   v=int(file.stem.split('_')[-1]);code=file.read_text();meta=load(file.with_suffix('.json'));assert digest(code)==meta['sha256'];dest=out/file.stem;dest.mkdir();shapes=None;reason=None
   try:
    shapes=Graph().parse(data=code,format='turtle')
    if meta.get('normalization') is None:reason='NO_ELIGIBLE_ORIGINAL_EXTRACTION; offline parsing gives no credit'
   except Exception as e:reason=type(e).__name__+': '+str(e)
   index.append(dict(version=v,sha256=meta['sha256'],origin=meta['origin'],parse_error=reason))
   for c in cases:
    d=dest/c['case_id'];d.mkdir();data=Graph().parse(inputs/Path(c['fixture']).name);oc=oracle(data,'IMO-001');assert oc['conforms']==(c['expected']=='PASS')
    verdict,report=validate_pair_graph(data,shapes,schema) if not reason else (dict(conforms=None,error=reason),None)
    if report is not None:report.serialize(d/'report.ttl',format='turtle')
    details=[]
    if report is not None:
     for result in report.subjects(RDF.type,SH.ValidationResult):
      source=report.value(result,SH.sourceShape);details.append(dict(node=str(result),focus=str(report.value(result,SH.focusNode)),path=str(report.value(result,SH.resultPath) or ''),value=str(report.value(result,SH.value) or ''),component=str(report.value(result,SH.sourceConstraintComponent)),source_shape=str(source),source_triples=sorted([[str(p),o.n3()] for p,o in (list(shapes.predicate_objects(source)) or list(report.predicate_objects(source)))]),details=[str(x) for x in report.objects(result,SH.detail)]))
    row=dict(label=LABEL,version=v,candidate_sha256=meta['sha256'],case_id=c['case_id'],expected=c['expected'],verdict=verdict,oracle=oc,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'),violation_details=details,reports_path=str(d.relative_to(group)),candidate_diagnostic=True)
    if c['expected']=='FAIL':
     fixed=Graph().parse(inputs/Path(c['counterfactual']).name);rc=oracle(fixed,'IMO-001');assert rc['conforms'] is True
     rv,rr=validate_pair_graph(fixed,shapes,schema) if not reason else (dict(conforms=None,error=reason),None)
     if rr is not None:rr.serialize(d/'repaired_report.ttl',format='turtle')
     status='NO_VERDICT' if verdict['conforms'] is None or rv['conforms'] is None else 'MISSED_INTENDED_DEFECT' if verdict['conforms'] else 'UNRELATED_OR_ADDITIONAL_FAILURE' if rv['conforms'] is False else 'PENDING_SEMANTIC_REVIEW'
     row.update(repaired_verdict=rv,repaired_oracle=rc,strict_provisional=status,certified_intent=c['source_review'])
    rows.append(row);write(d/'validation.json',row)
   write(out/'raw_results.json',rows);write(out/'candidate_index.json',index);print('EVALUATED candidate '+str(v),flush=True)
  write(out/'completion.json',dict(label=LABEL,status='EXTERNAL_VALIDATION_COMPLETE',elapsed_seconds=time.monotonic()-started,model_calls=0,evaluation_after_diagnostic=True,shape_transformations=[]))
 print(str(out),flush=True)
if __name__=='__main__':run()
