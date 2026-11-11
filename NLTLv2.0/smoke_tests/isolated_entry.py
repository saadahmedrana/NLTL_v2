"""Run the installed package while proving the old repository cannot be read."""
import pathlib,sys,os,json,runpy
root=pathlib.Path(sys.argv[1]).resolve();denied=pathlib.Path(sys.argv[2]).resolve();operation=sys.argv[3]
# This proof requires the external OS sandbox to deny the original repository.
try:
 with (denied/'MVP/SHACL_GENERATION_PIPELINE/pyproject.toml').open() as f:f.read(1)
except PermissionError:pass
else:raise RuntimeError('Original pipeline is accessible; isolation not established')
# Installed source must come from the fresh environment, never a path insertion.
import nltlv2
if denied in pathlib.Path(nltlv2.__file__).parents:raise RuntimeError('Old runtime import')
if any(str(denied) in x for x in sys.path):raise RuntimeError('Old sys.path entry')
runpy.run_path(str(root/'smoke_tests/isolation_check.py'))['inspect_tree'](root)
from nltlv2.cli import main
from nltlv2.core import stamp
sys.argv=['nltl','--project',str(root)]+(['smoke','--run-id',stamp()+'_isolated','--skip-core'] if operation=='smoke' else ['check'])
main()
