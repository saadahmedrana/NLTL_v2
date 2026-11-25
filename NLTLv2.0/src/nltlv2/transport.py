from __future__ import annotations
import json,os,pathlib,time
from .requests import assert_integrity
from .core import write
def provider_payload(request):
 payload=dict(model=request['model'],input=[dict(role='system',content=request['system']),dict(role='user',content=request['user'])],max_output_tokens=request['max_output_tokens'])
 if request.get('response_format'):
  if not request['route'].startswith('review'):raise ValueError('Structured output is reviewer-only')
  payload['text']={'format':request['response_format']}
 return payload
class ScriptedTransport:
 is_live=False
 def __init__(self,responses):self.responses=list(responses);self.calls=[]
 def dispatch(self,request,latest=None,expected_findings=None):
  if request['route'].endswith('repair'):assert_integrity(request,latest,expected_findings)
  self.calls.append(request)
  if not self.responses:raise RuntimeError('SCRIPT_EXHAUSTED')
  x=self.responses.pop(0)
  return dict(text=x,finish_reason='stop',usage={},elapsed_seconds=0) if isinstance(x,str) else x
class LiveTransport:
 is_live=True
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
  payload=provider_payload(request)
  # Verify the exact serialized content sent at the live boundary.
  rendered=json.loads(json.dumps(payload))
  if latest is not None and request['route'].endswith('repair'):
   copy=dict(request,user=rendered['input'][1]['content']);assert_integrity(copy,latest,expected_findings)
  if latest is not None and request['route'].startswith('review'):
   from .evidence import assert_review_packet
   data=json.loads(rendered['input'][1]['content']);assert_review_packet(data.get('original_request',data),latest)
  start=time.monotonic();r=requests.post(self.url,json=rendered,headers={'Ocp-Apim-Subscription-Key':self.key},timeout=180);r.raise_for_status();obj=r.json()
  text=obj.get('output_text') or ''.join(part.get('text','') for output in obj.get('output',[]) for part in output.get('content',[]) if part.get('type')=='output_text')
  return dict(text=text,status=obj.get('status'),finish_reason=(obj.get('incomplete_details') or {}).get('reason'),usage=obj.get('usage',{}),provider_response=obj,elapsed_seconds=time.monotonic()-start)


HOSTED_URL='https://ai-api-v2.aalto.fi/v1/responses'
HOSTED_MODEL='gpt-oss-120b'

def final_assistant_text(obj):
 """Typed assistant final text only. Never scrape reasoning or Harmony strings."""
 parts=[]
 for item in obj.get('output',[]):
  if item.get('type')!='message' or item.get('role')!='assistant':continue
  if item.get('channel') not in (None,'final'):continue
  for part in item.get('content',[]):
   if part.get('type')=='output_text' and isinstance(part.get('text'),str):parts.append(part['text'])
 return ''.join(parts)

class HostedResponsesTransport:
 is_live=True
 def __init__(self,*,enabled=False,project_root,output,max_calls,max_seconds,max_output_tokens_total,timeout=180,env_file=None,token_limits=None,token_counter=None):
  if not enabled or os.environ.get('NLTL_ALLOW_MODEL_CALLS')!='YES':raise RuntimeError('LIVE_MODEL_CALLS_DISABLED')
  import dotenv,requests
  p=pathlib.Path(env_file or os.environ.get('NLTL_ENV_FILE','')).expanduser().resolve()
  if not p.is_file() or p.is_relative_to(pathlib.Path(project_root).resolve()):raise ValueError('EXTERNAL_CREDENTIAL_CONFIGURATION_REQUIRED')
  env=dotenv.dotenv_values(p)
  self._key=env.get('AALTO_AI_API_KEY')
  if not self._key:raise ValueError('AALTO_AI_API_KEY_MISSING')
  configured=env.get('AALTO_AI_RESPONSES_URL')
  if configured and configured.rstrip('/')!=HOSTED_URL:raise ValueError('HOSTED_ENDPOINT_CONFIGURATION_MISMATCH')
  self.output=pathlib.Path(output);self.output.mkdir(parents=True,exist_ok=False)
  self.max_calls=max_calls;self.max_seconds=max_seconds;self.max_output_tokens_total=max_output_tokens_total;self.timeout=timeout
  self.token_limits=token_limits or {};self.token_counter=token_counter;self.dispatch_attempts=0
  if self.token_counter is None and self.token_limits.get('tokenizer_cache'):
   from .token_budget import load_counter
   self.token_counter=load_counter(project_root,self.token_limits)
  self.calls=0;self.reserved_output_tokens=0;self.started=time.monotonic();self.disabled=False
  self.session=requests.Session();self.session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
 def close(self):
  self.disabled=True;self.session.close()
 def dispatch(self,request,latest=None,expected_findings=None):
  if self.disabled:raise RuntimeError('DISPATCH_CLOSED')
  if request['model']!=HOSTED_MODEL:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')
  if request['route']=='fresh_regeneration':raise ValueError('FRESH_REGENERATION_DISABLED')
  if request['route'].endswith('repair'):assert_integrity(request,latest,expected_findings)
  payload=provider_payload(request)
  # Historical gateway protocol uses developer/user input_text blocks.
  payload['input']=[dict(role='developer' if x['role']=='system' else x['role'],content=[dict(type='input_text',text=x['content'])]) for x in payload['input']]
  payload.update(truncation='disabled',store=False)
  encoded=json.dumps(payload,ensure_ascii=False).encode('utf-8')
  from .token_budget import preflight
  self.dispatch_attempts+=1
  budget=preflight(payload,self.token_limits,self.token_counter);budget.update(request_bytes=len(encoded),route=request['route'],logical_dispatch_attempt=self.dispatch_attempts)
  write(self.output/f'attempt_{self.dispatch_attempts:03d}_token_budget.json',budget)
  (self.output/f'attempt_{self.dispatch_attempts:03d}_request.body').write_bytes(encoded)
  if latest is not None and request['route'].startswith('review'):
   from .evidence import assert_review_packet
   data=json.loads(payload['input'][1]['content'][0]['text']);assert_review_packet(data.get('original_request',data),latest)
  if budget['exceeds_known_token_limit']:raise RuntimeError('MODEL_CONTEXT_TOKEN_LIMIT_EXCEEDED_NO_TRUNCATION')
  if self.calls>=self.max_calls:raise RuntimeError('PROVIDER_CALL_LIMIT_EXHAUSTED')
  remaining=self.max_seconds-(time.monotonic()-self.started)
  if remaining<=0:raise RuntimeError('WORKFLOW_TIME_LIMIT_EXHAUSTED')
  if self.reserved_output_tokens+request['max_output_tokens']>self.max_output_tokens_total:raise RuntimeError('OUTPUT_TOKEN_LIMIT_EXHAUSTED')
  self.calls+=1;self.reserved_output_tokens+=request['max_output_tokens'];n=self.calls
  write(self.output/f'call_{n:03d}_request.json',dict(route=request['route'],payload=payload))
  (self.output/f'call_{n:03d}_request.body').write_bytes(encoded)
  write(self.output/'physical_calls.json',dict(started=self.calls,reserved_output_tokens=self.reserved_output_tokens,max_calls=self.max_calls))
  start=time.monotonic()
  try:
   r=self.session.post(HOSTED_URL,data=encoded,headers={'Authorization':'Bearer '+self._key,'Content-Type':'application/json'},timeout=min(self.timeout,remaining),allow_redirects=False)
  except Exception as e:
   write(self.output/f'call_{n:03d}_failure.json',dict(type=type(e).__name__,elapsed_seconds=time.monotonic()-start,no_retry=True))
   raise RuntimeError('HOSTED_TRANSPORT_FAILURE_'+type(e).__name__) from None
  elapsed=time.monotonic()-start
  # Never log auth/request headers. Scrub an echoed credential if a provider errs.
  raw=r.content.replace(self._key.encode(),b'[REDACTED_CREDENTIAL]')
  (self.output/f'call_{n:03d}_response.body').write_bytes(raw)
  write(self.output/f'call_{n:03d}_http.json',dict(status_code=r.status_code,elapsed_seconds=elapsed,credential_echo_redacted=raw!=r.content))
  if raw!=r.content:raise ValueError('PROVIDER_CREDENTIAL_ECHO_INTEGRITY_FAILURE')
  if r.status_code!=200:raise RuntimeError('HOSTED_HTTP_'+str(r.status_code))
  try:obj=json.loads(raw)
  except Exception:raise RuntimeError('HOSTED_INVALID_JSON') from None
  returned=obj.get('model');text=final_assistant_text(obj)
  response=dict(text=text,status=obj.get('status'),finish_reason=(obj.get('incomplete_details') or {}).get('reason') or obj.get('finish_reason'),usage=obj.get('usage'),provider_response=obj,returned_model=returned,identity_status='UNKNOWN' if returned is None else 'MATCH' if returned==HOSTED_MODEL else 'MISMATCH',elapsed_seconds=elapsed,physical_call=n,final_output_present=bool(text),token_budget=budget)
  actual_input=(obj.get('usage') or {}).get('input_tokens')
  response['token_budget']['actual_provider_input_tokens']=actual_input
  response['token_budget']['actual_input_minus_content_tokens']=None if actual_input is None or budget['supplied_text_tokens'] is None else actual_input-budget['supplied_text_tokens']
  write(self.output/f'call_{n:03d}_response.json',response)
  if returned is not None and returned!=HOSTED_MODEL:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')
  if obj.get('error') or obj.get('status') in ['failed','cancelled','queued','in_progress']:raise RuntimeError('HOSTED_RESPONSE_NOT_COMPLETED')
  # Incomplete output belongs to the existing bounded response-correction path.
  # A completed missing-final response remains a provider/protocol error.
  incomplete=response['status']=='incomplete' or (response['status'] is None and response['finish_reason'] in ['length','max_tokens','max_output_tokens'])
  if not text and not incomplete:raise RuntimeError('HOSTED_FINAL_OUTPUT_MISSING')
  return response
