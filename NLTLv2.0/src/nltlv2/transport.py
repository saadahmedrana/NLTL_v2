from __future__ import annotations
import json,os,pathlib,time
from .requests import assert_integrity
class ScriptedTransport:
 def __init__(self,responses):self.responses=list(responses);self.calls=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  if request['route'].endswith('repair'):assert_integrity(request,latest,expected_findings)
  self.calls.append(request)
  if not self.responses:raise RuntimeError('SCRIPT_EXHAUSTED')
  x=self.responses.pop(0)
  return dict(text=x,finish_reason='stop',usage={},elapsed_seconds=0) if isinstance(x,str) else x
class LiveTransport:
 """Explicit opt-in only; credentials are external and loaded only on construction."""
 def __init__(self,*,enabled=False,project_root=None):
  if not enabled or os.environ.get('NLTL_ALLOW_MODEL_CALLS')!='YES':raise RuntimeError('LIVE_MODEL_CALLS_DISABLED')
  import dotenv
  p=pathlib.Path(os.environ['NLTL_ENV_FILE']).expanduser().resolve()
  # No credential files inside a distributable project.
  if project_root is not None and p.is_relative_to(pathlib.Path(project_root).resolve()):raise ValueError('Credentials must be external')
  env=dotenv.dotenv_values(p);self.key=env['AALTO_API_KEY'];self.url=env['AALTO_RESPONSES_BASE_URL'].rstrip('/')

 def dispatch(self,request,latest=None,expected_findings=None):
  if request['route'].endswith('repair'):
   if expected_findings is None:raise ValueError('NO_INDEPENDENT_FEEDBACK_REFERENCE')
   assert_integrity(request,latest,expected_findings)
  if request['route']=='fresh_regeneration':raise ValueError('FRESH_REGENERATION_DISABLED')
  import requests
  payload=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
  # Verify the exact serialized content sent at the live boundary.
  rendered=json.loads(json.dumps(payload))
  if latest is not None and request['route'].endswith('repair'):
   copy=dict(request,user=rendered['input'][1]['content']);assert_integrity(copy,latest,expected_findings)
  start=time.monotonic();r=requests.post(self.url,json=rendered,headers={'Ocp-Apim-Subscription-Key':self.key},timeout=180);r.raise_for_status();obj=r.json()
  text=obj.get('output_text') or ''.join(part.get('text','') for output in obj.get('output',[]) for part in output.get('content',[]) if part.get('type')=='output_text')
  return dict(text=text,status=obj.get('status'),finish_reason=(obj.get('incomplete_details') or {}).get('reason'),usage=obj.get('usage',{}),provider_response=obj,elapsed_seconds=time.monotonic()-start)
