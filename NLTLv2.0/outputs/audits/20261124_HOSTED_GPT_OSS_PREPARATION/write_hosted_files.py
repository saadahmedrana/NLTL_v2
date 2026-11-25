from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
p=R/'src/nltlv2/runner.py';s=p.read_text();a=s.index("   result=blocked_result(self.cfg,rid,admission);");b=s.index('  self.admission_context=',a);s=s[:a]+"   result=blocked_result(self.cfg,rid,admission);write(self.output/'run.json',result);return result\n"+s[b:];p.write_text(s)
(R/'src/nltlv2/delivery.py').write_text('''"""Deterministic delivery/handoff; no model calls or evaluation imports."""
import hashlib,shutil
from .core import write

def finalize(output,history,terminal):
 integrity=terminal=='REQUEST_INTEGRITY_FAILURE'
 qualifying=[]
 for row in history:
  t=row.get('technical',{})
  if not t.get('qualifies'):continue
  p=output/f"candidate_{row['version']:02d}.ttl"
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('DELIVERY_CANDIDATE_INTEGRITY_FAILURE')
  qualifying.append(row)
 chosen=max(qualifying,key=lambda h:h['version']) if qualifying and not integrity else None
 status='NO_VERDICT' if chosen is None else 'ACCEPTED' if chosen.get('accepted') else 'UNVERIFIED'
 review=chosen.get('review') if chosen else None
 decision=(review or {}).get('decision')
 # Terminal review is preserved. This mapping is a handoff, not another review call.
 handoff='APPROVE' if status=='ACCEPTED' else 'REJECT' if status=='NO_VERDICT' or decision=='REJECT' else 'HUMAN_REVIEW_REQUIRED'
 result=dict(status=status,version=chosen['version'] if chosen else None,sha256=chosen['sha256'] if chosen else None,final_review=handoff,final_review_basis='Deterministic handoff from validated saved review and technical eligibility; no additional model review or repair',selected_review_decision=decision,terminal_review_decision=next((h['review']['decision'] for h in reversed(history) if h.get('review')),None),terminal_reason=terminal,selection_basis='Highest version passing fixed technical checks; no external scores',findings=chosen.get('findings',[]) if chosen else [],all_candidate_findings_preserved=True,correctness_certified=False)
 if chosen:shutil.copyfile(output/f"candidate_{chosen['version']:02d}.ttl",output/'delivered.ttl')
 write(output/'delivery.json',result);return result
''')
# Hosted transport is explicit and separate; existing Aalto route remains unchanged.
p=R/'src/nltlv2/transport.py'
p.write_text(p.read_text()+'''

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
 def __init__(self,*,enabled=False,project_root,output,max_calls,max_seconds,max_output_tokens_total,max_request_bytes=110000,timeout=180,env_file=None):
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
  self.max_calls=max_calls;self.max_seconds=max_seconds;self.max_output_tokens_total=max_output_tokens_total;self.max_request_bytes=max_request_bytes;self.timeout=timeout
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
  if len(encoded)>self.max_request_bytes:raise RuntimeError('REQUEST_CONTEXT_BYTE_LIMIT_EXCEEDED_NO_TRUNCATION')
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
  response=dict(text=text,status=obj.get('status'),finish_reason=(obj.get('incomplete_details') or {}).get('reason') or obj.get('finish_reason'),usage=obj.get('usage'),provider_response=obj,returned_model=returned,identity_status='UNKNOWN' if returned is None else 'MATCH' if returned==HOSTED_MODEL else 'MISMATCH',elapsed_seconds=elapsed,physical_call=n,final_output_present=bool(text))
  write(self.output/f'call_{n:03d}_response.json',response)
  if returned is not None and returned!=HOSTED_MODEL:raise ValueError('PROVIDER_MODEL_INTEGRITY_FAILURE')
  if obj.get('error') or obj.get('status') in ['failed','cancelled','queued','in_progress']:raise RuntimeError('HOSTED_RESPONSE_NOT_COMPLETED')
  if not text:raise RuntimeError('HOSTED_FINAL_OUTPUT_MISSING')
  return response
''')
print('Delivery and explicit hosted transport written.')
