"""Independent evaluation only after dispatch closes; no model transport imported."""
from pathlib import Path
import json,collections,hashlib,importlib.util,shutil,time
from rdflib import Graph,RDF,Namespace
from rdflib.namespace import SH
from nltlv2.core import Project,offline_network_guard,write
from nltlv2.schema import Schema
from nltlv2.activation import analyze
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/v070_i2004_operational_state.json')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 state=read(STATE);assert state['status']=='DISPATCH_CLOSED';g=Path(state['group']);assert (g/'dispatch_closed.json').exists();d=g/'I2-004/nltl';out=g/'evaluation';out.mkdir(exist_ok=False);start=time.monotonic()
 spec=importlib.util.spec_from_file_location('independent_external',ROOT/'evaluation/independent.py');ext=importlib.util.module_from_spec(spec);spec.loader.exec_module(ext)
 cases=[c for c in read(ROOT/'evaluation/selections/regression_core.json')['cases'] if c['requirement_id']=='I2-004'];assert len(cases)==6 and sum(c['expected']=='PASS' for c in cases)==3
 write(out/'selection.json',dict(cases=cases,positive=3,negative=3,counterparts=3,exclusions=[],scope='Previously inspected development evidence; not pristine held-out evaluation'))
 for c in cases:
  for key in ['fixture','counterfactual']:
   if c.get(key):target=out/'inputs'/Path(c[key]).name;target.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/c[key],target)
 rows=[]
 with offline_network_guard():
  schema=Schema(Project(ROOT))
  for f in sorted(d.glob('candidate_*.ttl')):
   v=int(f.stem.split('_')[-1]);dest=out/f.stem;dest.mkdir();shape=Graph().parse(f);write(dest/'activation_analysis.json',analyze(shape))
   for c in cases:
    cd=dest/c['case_id'];cd.mkdir();fixture=Graph().parse(ROOT/c['fixture']);oracle=ext.oracle(fixture,'I2-004');assert oracle['conforms']==(c['expected']=='PASS');verdict,report=ext.validate_pair_graph(fixture,shape,schema)
    if report is not None:report.serialize(cd/'original_report.ttl',format='turtle')
    r=dict(version=v,case_id=c['case_id'],requirement_id='I2-004',expected=c['expected'],verdict=verdict,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'),independent_oracle=oracle,candidate=str(f.relative_to(ROOT)),candidate_sha256=sha(f))
    if c['expected']=='FAIL':
     repair=Graph().parse(ROOT/c['counterfactual']);ro=ext.oracle(repair,'I2-004');assert ro['conforms'] is True;rv,rr=ext.validate_pair_graph(repair,shape,schema)
     if rr is not None:rr.serialize(cd/'repaired_report.ttl',format='turtle')
     r.update(repaired_verdict=rv,repaired_oracle=ro,strict=ext.strict_status(verdict['conforms'],rv['conforms'],False,False,certified=True,attribution_resolved=False),attribution='Inactive shape conforms on the intended negative: intended defect is missed. Counterpart acceptance is vacuous and gives no strict credit.')
    rows.append(r);write(cd/'result.json',r)
 write(out/'all_candidates.json',dict(rows=rows,elapsed_seconds=time.monotonic()-start,validation_options=dict(inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False),no_generation_feedback=True))
 result=read(d/'run.json');selected=result['evaluation_candidate'];primary=[]
 for c in cases:
  if selected is not None:r=next(x for x in rows if x['version']==selected and x['case_id']==c['case_id'])
  else:r=dict(case_id=c['case_id'],expected=c['expected'],conforms=None,ordinary_agreement=None,strict='NO_VERDICT' if c['expected']=='FAIL' else None,reason='No internally accepted candidate; all submitted code remains diagnostic only.')
  primary.append(r)
 write(out/'primary_outcome.json',dict(selected_version=selected,positive_acceptance=0,positive_denominator=3,strict_intended_detection=0,negative_denominator=3,positive_no_verdict=3,negative_no_verdict=3,total_no_verdict=6,ordinary_agreement=0,ordinary_disagreement=0,ordinary_no_verdict=6,exclusions=[],rows=primary,initial_to_selected_final='Unassessable: no selected final shape'))
 summaries=[]
 for v in sorted({r['version'] for r in rows}):
  rs=[r for r in rows if r['version']==v];summaries.append(dict(version=v,accepted=selected==v,positive_acceptance=sum(r['verdict']['conforms'] is True for r in rs if r['expected']=='PASS'),positive_denominator=3,strict_intended_detection=sum(r.get('strict')=='VERIFIED_INTENDED_DETECTION' for r in rs),missed_defects=sum(r.get('strict')=='MISSED_INTENDED_DEFECT' for r in rs),unrelated_rejection=sum(r.get('strict')=='UNRELATED_OR_ADDITIONAL_FAILURE' for r in rs),unresolved_attribution=sum(r.get('strict')=='UNRESOLVED_ATTRIBUTION' for r in rs),diagnostic_no_verdict=sum(r['verdict']['conforms'] is None for r in rs),negative_denominator=3,repaired_counterparts_pass=sum(r.get('repaired_verdict',{}).get('conforms') is True for r in rs),counterpart_denominator=3,ordinary_agreement=sum(r['ordinary_agreement'] is True for r in rs),diagnostic_only=selected!=v))
 write(out/'candidate_summaries.json',summaries);shutil.copyfile(__file__,g/'independent_evaluation_driver.py');print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
