"""Non-network pre-dispatch capture only. No live transport or credentials are imported."""
from pathlib import Path
import copy,hashlib,importlib.metadata,json,sys
STATE=Path('/private/tmp/v0100_authorized_continuation_state.json');state=json.loads(STATE.read_text());assert state['status']=='PREPARED';group=Path(state['group']);root=group.parents[2];snapshot=group/'snapshot';sys.path.insert(0,str(group/'runtime'))
from nltlv2.core import Project,Candidate,offline_network_guard,write
from nltlv2.runner import Runner
from nltlv2.tracking import Tracker
from nltlv2.checks import check,runtime_probe
from nltlv2.evidence import probe_summary
import nltlv2
assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.10.0';assert Path(nltlv2.__file__).parent==group/'runtime/nltlv2'
config=json.loads((group/'resolved_config.json').read_text());context=json.loads((group/'source_schema_context.json').read_text());out=group/'pre_dispatch_verified';out.mkdir(exist_ok=False);seed=(group/'I2-004/nltl/candidate_01.ttl').read_bytes();(out/'candidate_01.ttl').write_bytes(seed);candidate=Candidate(1,seed.decode(),'');assert candidate.sha256=='d8986fa2c5186ae5d619696650e5f56328480bc5c3430465c4fdbc1ef9d94f9a'
class Captured(Exception):pass
class NoNetworkTransport:
 is_live=False
 def dispatch(self,request,*args):
  assert request['route']=='review';self.request=copy.deepcopy(request);raise Captured('Undispatched packet captured; no provider implementation')
def barrier(event,args):
 if event in ['open','os.listdir','os.scandir'] and args and isinstance(args[0],(str,bytes)):
  path=Path(args[0]).resolve()
  if (path.is_relative_to(root) and not path.is_relative_to(group)) or path.is_relative_to(root.parent/'MVP') or any(path.is_relative_to(snapshot/folder) for folder in ['evaluation','tests','data/contracts','data/examples','schema/provenance','mappings','results']) or path.is_relative_to(group/'evaluation'):raise PermissionError('HISTORY_EVALUATION_SOLUTION_INACCESSIBLE')
sys.addaudithook(barrier)
with offline_network_guard():
 denied=[]
 for path in [root/'evaluation',root/'outputs/audits',root/'outputs/experiments',root.parent/'MVP',snapshot/'evaluation',snapshot/'tests',snapshot/'data/contracts',group/'evaluation']:
  try:path.open('rb')
  except PermissionError:denied.append(str(path))
  else:raise RuntimeError('BOUNDARY_NOT_ENFORCED')
 runner=Runner(Project(snapshot),config,NoNetworkTransport(),out);runner.admission_context=context['admission'];runner.input_hashes={name:h for name,h in json.loads((group/'snapshot_hashes.json').read_text()).items() if name.startswith(('data/','schema/','prompts/')) and name!='schema/runtime_lock.json'};tracker=Tracker();assert tracker.prior_semantic_issues()==[]
 findings=check(candidate,runner.schema,'I2-004',admission=context['admission']);execution,probe=runtime_probe(candidate,runner.schema);findings+=execution;runner.execution_summaries[1]=probe_summary(candidate,probe)
 try:runner.assess_candidate(candidate,context,None,{'status':'EXACT_SEED_UNCHANGED','changes':[]},tracker,findings,'I2-004')
 except Captured:pass
 else:raise RuntimeError('NO_PREPARED_REVIEW_PACKET')
 sizes=json.loads((out/'request_001_sizes.json').read_text());write(out/'pre_dispatch_verification.json',dict(version='0.10.0',source_runtime_identical=True,seed_sha256=candidate.sha256,approved_scope_sha256=json.loads((group/'preflight.json').read_text())['approved_scope_sha256'],all_resource_probes_denied=True,denied_paths=denied,initial_prior_issues=[],model_calls=0,credentials_read=False,request_rendered_bytes=sizes['rendered_bytes'],network='BLOCKED',not_live_run=True,dispatch_status='PENDING_DESTINATION_AND_PAYLOAD_APPROVAL'))
 print(json.dumps({'group':str(group),'preflight_review_bytes':sizes['rendered_bytes'],'resource_probes_denied':len(denied),'model_calls':0}))
