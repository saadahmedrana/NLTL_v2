from pathlib import Path
import sys,os,json,hashlib,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_REPLACEMENT_PREPARATION';sys.path.insert(0,str(A/'tokenizer_runtime'));os.environ['TIKTOKEN_CACHE_DIR']=str(A/'tokenizer_cache')
import tiktoken
enc=tiktoken.get_encoding('o200k_harmony')
files={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (A/'tokenizer_cache').glob('*') if p.is_file()}
profile=dict(encoding='o200k_harmony',tiktoken_version='0.12.0',regex_version='2025.11.3',cache_files=files,tokenizer_cache=str((A/'tokenizer_cache').relative_to(R)),model_context_tokens=131072,provider_context_tokens=None,provider_max_output_tokens=None,model_context_reference='https://huggingface.co/openai/gpt-oss-120b/blob/988e56b6fc3c723ad30aa7f18db742f54f921567/config.json',provider_limit_evidence='GET /v1/models confirmed model identity but did not expose limits or template; full provider framing/limit unknown',count_contract='Verified o200k_harmony encoding of every supplied text block. Full provider-added framing is not exposed; text count is a lower bound, not proof of exact complete input count.',no_silent_truncation=True)
(A/'token_limits.verified.json').write_text(json.dumps(profile,indent=2)+'\n');shutil.copy2('/tmp/hosted_tokenizer_install.log',A/'tokenizer_install.log');print(json.dumps(profile,indent=2));print('Tokenizer roundtrip',enc.decode(enc.encode('SHACL source schema scope'))=='SHACL source schema scope')
