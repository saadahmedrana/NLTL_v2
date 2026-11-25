"""Offline pilot preflight only: never loads credentials or opens a provider transport."""
import pathlib,json,hashlib,socket,sys,importlib.metadata
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def deny(*a,**k):raise RuntimeError('OFFLINE_NETWORK_DISABLED')
socket.create_connection=deny;socket.socket.connect=deny
manifest=load(HERE/'pilot_manifest.json')
for name,h in load(HERE/'frozen_resource_hashes.json').items():
 assert sha(ROOT/name)==h,'FROZEN_RESOURCE_CHANGED '+name
for name,h in load(HERE/'evaluation_resources.lock.json').items():
 assert sha(ROOT/name)==h,'EVALUATION_RESOURCE_CHANGED '+name
import nltlv2
assert nltlv2.__version__==importlib.metadata.version('nltlv2-refined')=='0.10.1'
assert pathlib.Path(nltlv2.__file__).is_relative_to(HERE/'runtime')
source={str(p.relative_to(ROOT/'src/nltlv2')):sha(p) for p in (ROOT/'src/nltlv2').rglob('*.py')}
installed={str(p.relative_to(HERE/'runtime/nltlv2')):sha(p) for p in (HERE/'runtime/nltlv2').rglob('*.py')}
assert source==installed
expected=load(HERE/'runtime_identity.json')['dependencies']
assert all(importlib.metadata.version(k)==v for k,v in expected.items())
from nltlv2.core import Project
from nltlv2.schema import Schema
from nltlv2.admission import load_admission
from nltlv2.requests import initial_request
from nltlv2.transport import provider_payload
project=Project(ROOT);schema=Schema(project);requests={}
for job in manifest['jobs']:
 assert not (ROOT/job['output']).exists(),'JOB_ALREADY_RESERVED_OR_RUN '+job['experiment_id']
 cfg=project.config(job['config']);admission=load_admission(project,cfg,schema,job['requirement_id']);assert admission['valid']
 ctx=schema.context(job['requirement_id']);ctx['admission']=admission['context'];ctx['scope']+=' External population/date eligibility and edition selection are supplied by caller admission, not independently inferred from RDF. Conditions within the represented requirement remain in scope; activation and query correctness are separate obligations.'
 settings={k:cfg[k] for k in ['model','generation_max_tokens','review_max_tokens']}
 req=initial_request(project,ctx,settings);req.update(model=cfg['model'],max_output_tokens=cfg['generation_max_tokens'])
 assert req==load(ROOT/job['initial_request']),'ACTUAL_INITIAL_REQUEST_DRIFT'
 requests.setdefault(job['requirement_id'],[]).append(provider_payload(req))
assert all(v[0]==v[1] for v in requests.values())
assert len(manifest['jobs'])==10 and sum(j['max_provider_calls'] for j in manifest['jobs'])==55
assert not (ROOT/manifest['batch_output']).exists(),'BATCH_ALREADY_RESERVED_OR_RUN'
print(json.dumps(dict(status='READY_UNDISPATCHED',pipeline_version='0.10.1',approved_scopes=5,identical_actual_initial_pairs=5,max_provider_calls=55,model_calls=0,dispatch_authorized=False)))
