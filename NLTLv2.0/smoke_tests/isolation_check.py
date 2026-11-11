"""Portable read/import isolation checks. OS sandbox is added by the isolation runner."""
import pathlib,sys,json,os

def inspect_tree(root):
 root=pathlib.Path(root).resolve();bad=[]
 for p in root.rglob('*'):
  if p.is_symlink():bad.append(str(p.relative_to(root))+': symlink')
  if p.is_file() and p.suffix in ['.py','.json','.toml','.ttl'] and not any(k in p.parts for k in ['outputs','build','__pycache__']):
   text=p.read_text(errors='replace')
   if '/'+'Users/' in text or '/'+'private/tmp/'+'nltlv20_build' in text:bad.append(str(p.relative_to(root))+': absolute workspace reference')
   if p.suffix=='.py' and ('from '+'nltl_'+'pipeline' in text or 'import '+'nltl_'+'pipeline' in text):bad.append(str(p.relative_to(root))+': old runtime import')
 if bad:raise AssertionError(bad)
 return dict(symlinks=0,absolute_old_workspace_references=0,old_runtime_imports=0)
if __name__=='__main__':
 print(json.dumps(inspect_tree(sys.argv[1]),indent=2))
