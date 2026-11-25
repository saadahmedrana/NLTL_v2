import importlib.util,pathlib,tempfile,json,contextlib,io,socket
L=pathlib.Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0/outputs/audits/20261125_TRF035_CLOSEOUT_REVIEW_COMPARISON/launcher');spec=importlib.util.spec_from_file_location('comparison_loop',L/'run_frozen_comparison.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def deny(*a,**k):raise RuntimeError('NETWORK_BLOCKED_OFFLINE_CONTROL')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=deny
m.preflight_check();realProject=m.Project;results=[]
for mode in ['valid','protocol_exhausted','infrastructure_stop']:
 temp=pathlib.Path(tempfile.mkdtemp(prefix='frozen_reviewer_loop_'))
 class TestProject(realProject):
  def output(self,kind,identifier):p=temp/identifier;p.mkdir();return p
 class Fake:
  is_live=False
  def __init__(self,**kw):self.calls=0;self.output=kw['output'];self.output.mkdir();self.closed=False
  def close(self):self.closed=True
  def dispatch(self,q,*args):
   self.calls+=1;assert self.calls<=4
   if mode=='infrastructure_stop':raise RuntimeError('HOSTED_TRANSPORT_FAILURE_Control')
   wire=json.loads(q['user']);raw=dict(assessment='APPROVE',issues=[],questions=[],gap_review=[dict(id=x['id'],material=False,why='Software route control only') for x in wire['retrieval_gaps']])
   if mode=='protocol_exhausted':text='{}'
   else:
    # A minimal software-only coverage assertion, not substantive/accuracy evidence.
    source=next(e for e in wire['evidence_catalog']['entries'] if e['kind']=='SOURCE');raw['coverage']=[dict(criterion='Synthetic interface control',kind='INPUT_READINESS',status='IMPLEMENTED',evidence=[source['evidence_id']],locations=[dict(start=1,end=1,unit='lines')],explanation='Format/route control only')];text=json.dumps(raw)
   return dict(text=text,status='completed',elapsed_seconds=0,usage={})
 m.Project=TestProject;m.HostedResponsesTransport=Fake
 with contextlib.redirect_stdout(io.StringIO()) as log:
  try:m.run(mode)
  except SystemExit as e:assert mode=='infrastructure_stop' and e.code==2
 out=temp/mode;receipt=json.loads((out/'dispatch_closed.json').read_text());progress=json.loads((out/'progress.json').read_text());assert receipt['dispatch_closed'] and progress['in_progress']==0 and 'done=' in log.getvalue()
 if mode=='valid':assert receipt['physical_calls']==2 and len(receipt['results'])==2 and all(r['status']=='VALID_REVIEW_NOT_CORRECTNESS_CERTIFICATION' for r in receipt['results'])
 if mode=='protocol_exhausted':assert receipt['physical_calls']==4 and len(receipt['results'])==2 and all(r['status']=='REVIEWER_RESPONSE_PROTOCOL_FAILURE' for r in receipt['results'])
 if mode=='infrastructure_stop':assert receipt['physical_calls']==1 and receipt['not_run']==['B_generic_coverage'] and receipt['results'][0]['status']=='ERROR'
 results.append(dict(control=mode,status='PASS',scripted_dispatches=receipt['physical_calls'],real_provider_calls=0,done=progress['done'],pending=progress['pending'],temporary_output=str(out)))
print(json.dumps(dict(label='OFFLINE_SCRIPTED_LOOP_CONTROLS_NO_WORKFLOW_OR_ACCURACY_CREDIT',status='PASS',model_calls=0,controls=results),indent=2))
