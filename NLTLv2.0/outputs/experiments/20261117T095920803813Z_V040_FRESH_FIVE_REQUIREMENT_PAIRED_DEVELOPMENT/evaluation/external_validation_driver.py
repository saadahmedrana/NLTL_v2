"""External post-generation validation only. Never imported by generation or repair.
No shape transformations; strict attribution is a separate evidence review.
"""
from pathlib import Path
import collections,json,hashlib,shutil,time
from rdflib import Graph,RDF
from rdflib.namespace import SH
from nltlv2.core import Project,load,write,offline_network_guard,digest
from nltlv2.schema import Schema
from nltlv2.evaluation import oracle,validate_pair_graph
STATE=Path('/private/tmp/five_v040_pilot_state_20261117.json');ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def run():
 state=load(STATE);assert state['status'] in ['GENERATION_COMPLETE','STOPPED_SAFETY'];group=Path(state['group']);out=group/'evaluation';out.mkdir(exist_ok=False);shutil.copyfile(__file__,out/'external_validation_driver.py');manifest=load(group/'execution_manifest.json');cases=load(ROOT/manifest['evaluation']['selection'])['cases'];assert len(cases)==30
 write(out/'reviewed_selection.json',dict(cases=cases,version='0.4.0',exclusions=[],scope='30 development cases and 16 counterparts; not a representative held-out sample'))
 for path,h in manifest['evaluation_hashes'].items():assert sha(ROOT/path)==h
 inputs=out/'inputs';inputs.mkdir()
 for c in cases:
  for k in ['fixture','counterfactual']:
   if c.get(k):assert sha(ROOT/c[k])==c[k+'_sha256'];shutil.copyfile(ROOT/c[k],inputs/Path(c[k]).name)
 p=Project(group/'snapshot');schema=Schema(p);rows=[];candidate_index=[];start=time.monotonic()
 write(out/'validation_options.json',dict(inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False,ontology_sha256=sha(group/'snapshot/schema/Schema_for_NLTL.ttl'),version='0.4.0',feedback_to_repair=False,shape_transformations=[]))
 with offline_network_guard():
  for rid in manifest['requirements']:
   for method,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
    work=group/rid/folder
    for file in sorted(work.glob('candidate_*.ttl')):
     v=int(file.stem.split('_')[-1]);code=file.read_text();metadata=load(file.with_suffix('.json'));assert digest(code)==metadata['sha256'];dest=out/rid/folder/file.stem;dest.mkdir(parents=True);reason=None
     try:
      shapes=Graph().parse(data=code,format='turtle')
      if metadata.get('normalization') is None:reason='ORIGINAL_EXTRACTION_FAILED; offline parse gives no workflow credit'
     except Exception as e:shapes=None;reason=type(e).__name__+': '+str(e)
     eligible=reason is None;index=dict(requirement_id=rid,method=method,version=v,sha256=digest(code),eligible=eligible,no_verdict_reason=reason,candidate_path=str(file.relative_to(group)));candidate_index.append(index)
     for c in cases:
      if c['requirement_id']!=rid:continue
      d=dest/c['case_id'];d.mkdir();data=Graph().parse(inputs/Path(c['fixture']).name);oc=oracle(data,rid);assert oc['conforms']==(c['expected']=='PASS')
      verdict,report=validate_pair_graph(data,shapes,schema) if eligible else (dict(conforms=None,error=reason),None)
      if report is not None:report.serialize(d/'report.ttl',format='turtle')
      details=[]
      if report is not None:
       for result in report.subjects(RDF.type,SH.ValidationResult):
        source=report.value(result,SH.sourceShape);details.append(dict(result_node=str(result),focus=str(report.value(result,SH.focusNode)),path=str(report.value(result,SH.resultPath) or ''),value=str(report.value(result,SH.value) or ''),component=str(report.value(result,SH.sourceConstraintComponent)),source_shape=str(source),source_triples=sorted([[str(pr),obj.n3()] for pr,obj in shapes.predicate_objects(source)]),details=[str(x) for x in report.objects(result,SH.detail)]))
      row=dict(requirement_id=rid,method=method,version=v,candidate_sha256=digest(code),case_id=c['case_id'],expected=c['expected'],verdict=verdict,original_oracle=oc,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'),violation_details=details,reports_path=str(d.relative_to(group)),diagnostic_only=True)
      if c['expected']=='FAIL':
       fixed=Graph().parse(inputs/Path(c['counterfactual']).name);rc=oracle(fixed,rid);assert rc['conforms'] is True
       rv,rr=validate_pair_graph(fixed,shapes,schema) if eligible else (dict(conforms=None,error=reason),None)
       if rr is not None:rr.serialize(d/'repaired_report.ttl',format='turtle')
       row.update(repaired_verdict=rv,repaired_oracle=rc,intended=c['source_review'],strict_provisional='NO_VERDICT' if verdict['conforms'] is None or rv['conforms'] is None else 'MISSED_INTENDED_DEFECT' if verdict['conforms'] else 'UNRELATED_OR_ADDITIONAL_FAILURE' if rv['conforms'] is False else 'PENDING_SEMANTIC_ADJUDICATION')
      rows.append(row);write(d/'validation.json',row)
     print('EVALUATED '+rid+' '+method+' candidate='+str(v),flush=True)
     write(out/'candidate_index.json',candidate_index);write(out/'raw_results.json',rows)
  write(out/'validation_completion.json',dict(status='EXTERNAL_VALIDATION_COMPLETE',generation_was_closed=state['status'],model_calls=0,elapsed_seconds=time.monotonic()-start,candidates=len(candidate_index),rows=len(rows),negative_rows=sum(r['expected']=='FAIL' for r in rows),source='Frozen v0.4.0 shapes; no transformations; semantics review follows'))
 print(str(out),flush=True)
if __name__=='__main__':run()
