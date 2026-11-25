from pathlib import Path
import hashlib,json,shutil
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261124_HOSTED_GPT_OSS_16K_PREPARATION';A.mkdir(exist_ok=False)
(A/'protected_before.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and not p.is_relative_to(A)},indent=2))
for name in ['src/nltlv2/transport.py','src/nltlv2/runner.py','src/nltlv2/__init__.py','pyproject.toml']:
 dest=A/'original'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/name,dest)
p=R/'src/nltlv2/transport.py';s=p.read_text();old="  if not text:raise RuntimeError('HOSTED_FINAL_OUTPUT_MISSING')";new="""  # Incomplete output belongs to the existing bounded response-correction path.
  # A completed missing-final response remains a provider/protocol error.
  incomplete=response['status']=='incomplete' or (response['status'] is None and response['finish_reason'] in ['length','max_tokens','max_output_tokens'])
  if not text and not incomplete:raise RuntimeError('HOSTED_FINAL_OUTPUT_MISSING')""";assert old in s;s=s.replace(old,new);p.write_text(s)
for name in ['src/nltlv2/runner.py','src/nltlv2/__init__.py','pyproject.toml']:
 p=R/name;p.write_text(p.read_text().replace('0.11.1','0.11.2'))
print('Only incomplete-final routing and version declarations changed. Reviewer16k will be frozen in the new hosted manifest.')
