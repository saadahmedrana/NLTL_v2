"""Verified content-token accounting; provider-added framing stays explicitly unknown."""
import hashlib,os,pathlib

def load_counter(root,limits):
 import tiktoken
 import importlib.metadata
 if importlib.metadata.version('tiktoken')!=limits['tiktoken_version']:raise ValueError('TOKENIZER_VERSION_INTEGRITY_FAILURE')
 cache=(pathlib.Path(root)/limits['tokenizer_cache']).resolve()
 for name,sha in limits['cache_files'].items():
  path=(pathlib.Path(root)/name).resolve()
  if not path.is_file() or path.parent!=cache or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('TOKENIZER_CACHE_INTEGRITY_FAILURE')
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
