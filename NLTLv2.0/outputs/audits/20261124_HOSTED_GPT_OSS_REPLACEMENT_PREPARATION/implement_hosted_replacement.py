from pathlib import Path
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0')
(R/'src/nltlv2/token_budget.py').write_text('''"""Verified content-token accounting; provider-added framing stays explicitly unknown."""
import hashlib,os,pathlib

def load_counter(root,limits):
 import tiktoken
 import importlib.metadata
 if importlib.metadata.version('tiktoken')!=limits['tiktoken_version']:raise ValueError('TOKENIZER_VERSION_INTEGRITY_FAILURE')
 cache=(pathlib.Path(root)/limits['tokenizer_cache']).resolve()
 for name,sha in limits['cache_files'].items():
  path=(pathlib.Path(root)/name).resolve()
  if path.parent!=cache or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('TOKENIZER_CACHE_INTEGRITY_FAILURE')
 if not limits['cache_files']:raise ValueError('TOKENIZER_CACHE_INTEGRITY_FAILURE')
 # Cache presence/hash checked first: get_encoding must not fetch any resource.
 os.environ['TIKTOKEN_CACHE_DIR']=str(cache)
 encoding=tiktoken.get_encoding(limits['encoding'])
 return lambda text:len(encoding.encode(text,disallowed_special=()))

def preflight(payload,limits,counter=None):
 texts=[p['text'] for item in payload['input'] for p in item['content'] if p.get('type')=='input_text']
 count=sum(counter(text) for text in texts) if counter is not None else None
 known=[n for n in [limits.get('model_context_tokens'),limits.get('provider_context_tokens')] if n is not None]
 context=min(known) if known else None;reserved=payload['max_output_tokens']
 exceeds=(count is not None and context is not None and count+reserved>context) or (limits.get('provider_max_output_tokens') is not None and reserved>limits['provider_max_output_tokens'])
 return dict(encoding=limits.get('encoding'),supplied_text_tokens=count,input_text_count_verified=count is not None,complete_provider_input_count_verified=False,provider_framing_tokens=None,requested_output_tokens=reserved,input_plus_output_lower_bound=None if count is None else count+reserved,model_context_tokens=limits.get('model_context_tokens'),provider_context_tokens=limits.get('provider_context_tokens'),provider_max_output_tokens=limits.get('provider_max_output_tokens'),exceeds_known_token_limit=exceeds,status='EXCEEDS_KNOWN_TOKEN_LIMIT' if exceeds else 'CONTENT_COUNT_WITHIN_LIMIT_PROVIDER_FRAMING_UNVERIFIED' if count is not None else 'TOKEN_COUNT_UNAVAILABLE_PROVIDER_ENFORCES_LIMIT',uncertainty='Provider-added framing, deployed tokenizer revision and any lower provider limit are not exposed. Count is verified for supplied text under pinned public tokenizer, not claimed exact full provider input. Provider context rejection is terminal; truncation stays disabled.',material_context_truncated=False)
''')
p=R/'src/nltlv2/transport.py';s=p.read_text().replace('max_output_tokens_total,max_request_bytes=110000,timeout=180,env_file=None','max_output_tokens_total,timeout=180,env_file=None,token_limits=None,token_counter=None')
s=s.replace('self.max_output_tokens_total=max_output_tokens_total;self.max_request_bytes=max_request_bytes;self.timeout=timeout','self.max_output_tokens_total=max_output_tokens_total;self.timeout=timeout\n  self.token_limits=token_limits or {};self.token_counter=token_counter;self.dispatch_attempts=0\n  if self.token_counter is None and self.token_limits.get(\'tokenizer_cache\'):\n   from .token_budget import load_counter\n   self.token_counter=load_counter(project_root,self.token_limits)')
s=s.replace("  if len(encoded)>self.max_request_bytes:raise RuntimeError('REQUEST_CONTEXT_BYTE_LIMIT_EXCEEDED_NO_TRUNCATION')", """  from .token_budget import preflight
  self.dispatch_attempts+=1
  budget=preflight(payload,self.token_limits,self.token_counter);budget.update(request_bytes=len(encoded),route=request['route'],logical_dispatch_attempt=self.dispatch_attempts)
  write(self.output/f'attempt_{self.dispatch_attempts:03d}_token_budget.json',budget)
  (self.output/f'attempt_{self.dispatch_attempts:03d}_request.body').write_bytes(encoded)
  if latest is not None and request['route'].startswith('review'):
   from .evidence import assert_review_packet
   data=json.loads(payload['input'][1]['content'][0]['text']);assert_review_packet(data.get('original_request',data),latest)
  if budget['exceeds_known_token_limit']:raise RuntimeError('MODEL_CONTEXT_TOKEN_LIMIT_EXCEEDED_NO_TRUNCATION')""")
s=s.replace("physical_call=n,final_output_present=bool(text))", "physical_call=n,final_output_present=bool(text),token_budget=budget)")
s=s.replace("  write(self.output/f'call_{n:03d}_response.json',response)", """  actual_input=(obj.get('usage') or {}).get('input_tokens')
  response['token_budget']['actual_provider_input_tokens']=actual_input
  response['token_budget']['actual_input_minus_content_tokens']=None if actual_input is None or budget['supplied_text_tokens'] is None else actual_input-budget['supplied_text_tokens']
  write(self.output/f'call_{n:03d}_response.json',response)""")
p.write_text(s)
p=R/'src/nltlv2/hosted_pilot.py';s=p.read_text().replace("max_request_bytes=m['max_request_bytes'],timeout=m['request_timeout_seconds']", "token_limits=m['token_limits'],timeout=m['request_timeout_seconds']")
s=s.replace(" if not a.allow_model_calls:"," if m.get('dispatch_ready') is not True:raise ValueError('EXPERIMENT_NOT_READY')\n if not a.allow_model_calls:")
s=s.replace("status=delivery.get('status','NO_VERDICT')", "status=delivery.get('status','NOT_RUN' if not result else 'NO_VERDICT')")
p.write_text(s)
p=R/'src/nltlv2/runner.py';s=p.read_text()
s=s.replace('self.active_review_body=None','self.active_review_body=None;self.physical_calls_start=getattr(transport,\'calls\',None) if isinstance(getattr(transport,\'calls\',None),int) else None')
s=s.replace('attempt_start=time.monotonic();metrics_start=len(self.response_metrics)','attempt_start=time.monotonic();metrics_start=len(self.response_metrics);c=None;technical=None;fs=[];changes=None')
s=s.replace(";write(self.output/'operational_failure.json',operational);break", """;write(self.output/'operational_failure.json',operational)
    if c is not None and not any(h['version']==c.version for h in history):
     row=dict(attempt=attempt,version=c.version,sha256=c.sha256,status=status,accepted=False,technical=technical or {},findings=[f.asdict() for f in fs],review=None,interrupted=True,terminal_reason=operational,structural_change_manifest=changes,elapsed_seconds=time.monotonic()-attempt_start,request_metrics=self.response_metrics[metrics_start:])
     history.append(row);write(self.output/'history.json',history);write(self.output/f'findings_{attempt:02d}.json',row['findings']);self.transition(c,status,operational_failure=operational)
    break""")
s=s.replace("provider_calls=len(self.calls) if getattr(self.transport,'is_live',False) else 0", "provider_calls=(self.transport.calls-self.physical_calls_start if self.physical_calls_start is not None else len(self.calls)) if getattr(self.transport,'is_live',False) else 0")
s=s.replace("candidate_attempts=len(history)","candidate_attempts=len(list(self.output.glob('candidate_*.ttl')))")
s=s.replace("1 if self.cfg['method']=='Single-shot' and history and history[0]['status']!='FORMAT_ERROR' else None", "1 if self.cfg['method']=='Single-shot' and history else None")
s=s.replace("version='0.11.0'","version='0.11.1'");p.write_text(s)
for name in ['src/nltlv2/__init__.py','pyproject.toml']:
 p=R/name;p.write_text(p.read_text().replace('0.11.0','0.11.1'))
print('Focused token/physical-accounting/interrupted-candidate integration fixes applied.')
