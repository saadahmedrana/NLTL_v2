"""Independent offline reference evaluation; never imported by production."""
import argparse,json
from pathlib import Path
from nltlv2.core import Project,offline_network_guard
from independent import core_regression,evaluate
p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);p.add_argument('--shape-manifest');a=p.parse_args();project=Project(a.project);out=project.path(a.output);out.mkdir(parents=True,exist_ok=False)
with offline_network_guard():result=evaluate(project,a.shape_manifest,out) if a.shape_manifest else core_regression(project,out)
print(json.dumps({k:v for k,v in result.items() if k not in ['rows']},indent=2))
