from pathlib import Path
import json,hashlib,requests,os,time
from dotenv import dotenv_values
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';A.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
(A/'protected_before.json').write_text(json.dumps({str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(A)},indent=2))
for name in ['src/nltlv2/transport.py','src/nltlv2/runner.py','src/nltlv2/hosted_pilot.py','src/nltlv2/__init__.py','pyproject.toml','evaluation/evaluate_hosted_shared_start.py','tests/test_hosted_shared_start.py']:
 p=A/'original'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((R/name).read_bytes())
env=dotenv_values(os.environ.get('NLTL_ENV_FILE','/Users/sadisfaction570/Desktop/Journal 1/env/NLTL_v2.env'));key=env['AALTO_AI_API_KEY']
s=requests.Session();s.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
start=time.monotonic();r=s.get('https://ai-api-v2.aalto.fi/v1/models',headers={'Authorization':'Bearer '+key},timeout=30,allow_redirects=False)
raw=r.content.replace(key.encode(),b'[REDACTED_CREDENTIAL]');(A/'provider_models.response.json').write_bytes(raw)
matching=[]
if r.status_code==200:
 data=r.json();matching=[x for x in data.get('data',[]) if x.get('id') in ['gpt-oss-120b','openai/gpt-oss-120b']]
info=dict(url='https://ai-api-v2.aalto.fi/v1/models',status_code=r.status_code,elapsed_seconds=time.monotonic()-start,model_inference_calls=0,metadata_HTTP_calls=1,matching_models=matching)
(A/'provider_metadata_probe.json').write_text(json.dumps(info,indent=2));print(json.dumps(info,indent=2))
for name,version in [('tiktoken','0.12.0'),('regex','2025.11.3')]:
 rr=s.get('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=30);print(name,version,rr.status_code)
 if rr.status_code==200:(A/(name+'_pypi.json')).write_text(json.dumps(rr.json()))
rev='988e56b6fc3c723ad30aa7f18db742f54f921567'
for name in ['config.json','chat_template.jinja','tokenizer_config.json']:
 url='https://huggingface.co/openai/gpt-oss-120b/resolve/'+rev+'/'+name;rr=s.get(url,timeout=45)
 (A/('upstream_'+name)).write_bytes(rr.content);print('upstream',name,rr.status_code,len(rr.content))
 if name=='config.json' and rr.status_code==200:print('upstream_model_context',rr.json().get('max_position_embeddings'))
s.close()
