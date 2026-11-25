"""Independent offline evaluation after generation dispatch has closed."""
from pathlib import Path
import sys,json,collections,hashlib,shutil,importlib.util,time
from rdflib import Graph,URIRef,RDF
from rdflib.namespace import SH
from nltlv2.core import Project,offline_network_guard
from nltlv2.schema import Schema
ROOT=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');STATE=Path('/private/tmp/v060_live_pilot_state_20261120_retry1.json');RIDS=['I2-004','I2-005','IMO-001','TRF-010','TRF-035']
def read(p):return json.loads(p.read_text())
def write(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 state=read(STATE);assert state['status'] in ['GENERATION_COMPLETE','STOPPED'];g=Path(state['group']);assert (g/'dispatch_closed.json').is_file()
 out=g/'evaluation';out.mkdir(exist_ok=False);started=time.monotonic()
 spec=importlib.util.spec_from_file_location('independent_external',ROOT/'evaluation/independent.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 core=read(ROOT/'evaluation/selections/regression_core.json');cases=[c for c in core['cases'] if c['requirement_id'] in RIDS];assert len(cases)==30;assert sum(c['expected']=='FAIL' for c in cases)==16
 write(out/'selection.json',dict(cases=cases,positive=14,negative=16,counterparts=16,exclusions={'Single-shot':[],'NLTL':[]},original_selection_sha256=sha(ROOT/'evaluation/selections/regression_core.json'),exposure='Inspected development evidence, not held-out evaluation'))
 for c in cases:
  for k in ['fixture','counterfactual']:
   if c.get(k):dest=out/'inputs'/Path(c[k]).name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/c[k],dest)
 with offline_network_guard():
  schema=Schema(Project(ROOT));rows=[];histories={};shape_errors=[]
  for rid in RIDS:
   for wf,folder in [('Single-shot','single_shot'),('NLTL','nltl')]:
    dest=g/rid/folder
    if (dest/'run.json').exists():histories[(rid,wf)]=read(dest/'run.json')
    for f in sorted(dest.glob('candidate_*.ttl')):
     version=int(f.stem.split('_')[-1]);print('EVALUATE '+rid+' '+wf+' v'+str(version),flush=True);cd=out/rid/folder/f.stem;cd.mkdir(parents=True)
     try:
      shape=Graph().parse(f);shape.serialize(cd/'parsed_shape.ttl',format='turtle')
      index={str(s):[dict(predicate=str(p),object=o.n3()) for p,o in shape.predicate_objects(s)] for s in set(shape.subjects())};write(cd/'shape_index.json',index);error=None
     except Exception as e:shape=None;index={};error=type(e).__name__+': '+str(e);shape_errors.append(dict(requirement_id=rid,workflow=wf,version=version,error=error))
     for c in [x for x in cases if x['requirement_id']==rid]:
      case_dir=cd/c['case_id'];case_dir.mkdir();fixture=Graph().parse(ROOT/c['fixture']);oc=mod.oracle(fixture,rid);assert oc['conforms']==(c['expected']=='PASS'),c['case_id']
      verdict,report=mod.validate_pair_graph(fixture,shape,schema) if shape is not None else (dict(conforms=None,error=error),None)
      if report is not None:report.serialize(case_dir/'original_report.ttl',format='turtle')
      row=dict(requirement_id=rid,workflow=wf,version=version,case_id=c['case_id'],expected=c['expected'],candidate=str(f.relative_to(ROOT)),candidate_sha256=sha(f),verdict=verdict,ordinary_agreement=None if verdict['conforms'] is None else verdict['conforms']==(c['expected']=='PASS'),oracle=oc,violations_with_constraint_evidence=[dict(v,constraint=index.get(v['source_shape'],[])) for v in verdict.get('violations',[])])
      if c['expected']=='FAIL':
       repair=Graph().parse(ROOT/c['counterfactual']);ro=mod.oracle(repair,rid);assert ro['conforms'] is True,c['case_id'];rv,rr=mod.validate_pair_graph(repair,shape,schema) if shape is not None else (dict(conforms=None,error=error),None)
       if rr is not None:rr.serialize(case_dir/'repaired_report.ttl',format='turtle')
       status=mod.strict_status(verdict['conforms'],rv['conforms'],False,False,certified=True,attribution_resolved=False)
       row.update(repaired_verdict=rv,repaired_oracle=ro,strict=status,attribution='Provisional conservative status. Unreviewed query/wrapper meanings remain unresolved; negative rejection alone earns no strict credit.',repaired_violations_with_constraint_evidence=[dict(v,constraint=index.get(v['source_shape'],[])) for v in rv.get('violations',[])])
      rows.append(row);write(case_dir/'result.json',row)
     write(out/'all_candidates_progress.json',rows)
  write(out/'all_candidates.json',dict(rows=rows,parse_errors=shape_errors,evaluation_elapsed_seconds=time.monotonic()-started,source='Unchanged reviewed 30-case selection and independent oracle; no production feedback',validation_options=dict(inference='rdfs',advanced=True,abort_on_first=False,allow_infos=False,allow_warnings=False,meta_shacl=False,inplace=False)))
 print('EVALUATION_COMPLETE '+str(out),flush=True)
if __name__=='__main__':main()
