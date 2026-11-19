"""Offline diagnostic replay of approved development candidates, never fresh accuracy."""
from .core import Project,GenerationProject,Candidate,load,write,digest,stamp
from .schema import Schema
from .checks import check
from .development_checks import assess
from .tracking import Tracker
from .requests import repair_request,assert_integrity
import hashlib

def replay(project,manifest_path,rid,run_id=None):
 if not manifest_path.startswith('smoke_tests/regression_inputs/'):raise ValueError('Replay inputs must be approved development inputs')
 source=GenerationProject(project.root);schema=Schema(source);manifest=load(source.path(manifest_path));tracker=Tracker()
 if hashlib.sha256(source.path('data/contracts/development_witness_contracts.json').read_bytes()).hexdigest()!=manifest['source_contract_sha256']:raise ValueError('Original development witnesses changed')
 if hashlib.sha256(source.path('schema/Schema_for_NLTL.ttl').read_bytes()).hexdigest()!=manifest['schema_sha256']:raise ValueError('Replay schema changed')
 out=project.output('audits',run_id or stamp()+'_CANDIDATE_REPLAY_V040');history=[]
 for item in manifest['candidates']:
  if not item['file'].startswith('smoke_tests/regression_inputs/'):raise ValueError('Non-development candidate in replay')
  code=source.path(item['file']).read_text();c=Candidate(item['version'],code,code)
  if c.sha256!=item['sha256']:raise ValueError('Replay candidate is not byte-identical')
  folder=out/f'candidate_{c.version:02d}';folder.mkdir();(folder/'candidate.ttl').write_text(code)
  fs=check(c,schema,rid);bf,coverage=assess(c,schema,rid);fs+=bf
  changes,summary=tracker.observe(c,fs,coverage,static_complete=not any(f.category=='PARSE_ERROR' for f in fs))
  write(folder/'findings.json',[f.asdict() for f in fs]);write(folder/'coverage.json',coverage);write(folder/'reconciliation.json',changes);write(folder/'persistent_failure_summary.json',summary)
  if any(f.blocking for f in fs):
   request=repair_request(source,schema.context(rid),c,fs,persistent_summary=summary);write(folder/'repair_request.json',request);write(folder/'request_integrity.json',assert_integrity(request,c,fs));(folder/'repair_request.rendered.txt').write_text(request['system']+'\n\n--- USER ---\n'+request['user'])
  history.append(dict(version=c.version,sha256=c.sha256,behavior_status=coverage['status'],failed_witness_ids=[w['witness_id'] for w in coverage.get('witnesses',[]) if w['status']=='CONFIRMED_COUNTEREXAMPLE'],unassessable_witness_ids=[w['witness_id'] for w in coverage.get('witnesses',[]) if w['status'].startswith('UNASSESSABLE') or w['status']=='UNRESOLVED_EXECUTION'],changes=changes,repeat_detection=summary['repeat_detection']))
  write(out/'summary.json',dict(version='0.4.0',arm='BYTE_IDENTICAL_DEVELOPMENT_REPLAY_NOT_GENERATION',model_calls=0,external_evaluation_inputs=False,requirement_id=rid,history=history))
 return dict(output=str(out.relative_to(project.root)),candidates=len(history),model_calls=0)
