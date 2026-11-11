from __future__ import annotations
import argparse,json,pathlib,unittest,io,os,sys
from .core import Project,write,load,stamp,offline_network_guard
from .schema import Schema
from .mappings import verify
from .study import prepare_selection,budget_analysis

def main():
 p=argparse.ArgumentParser();p.add_argument('--project',default='.');sub=p.add_subparsers(dest='command',required=True)
 s=sub.add_parser('smoke');s.add_argument('--run-id',default=None);s.add_argument('--skip-core',action='store_true')
 sub.add_parser('check');sub.add_parser('schema-audit');sub.add_parser('prepare-study')
 g=sub.add_parser('run');g.add_argument('--config',required=True);g.add_argument('--requirement',required=True);g.add_argument('--experiment-id',required=True);g.add_argument('--script');g.add_argument('--allow-model-calls',action='store_true')
 e=sub.add_parser('evaluate-core');e.add_argument('--run-id')
 v=sub.add_parser('evaluate');v.add_argument('--shape-manifest',required=True);v.add_argument('--experiment-id',required=True)
 a=sub.add_parser('analyze-budgets');a.add_argument('histories',nargs='+');a.add_argument('--experiment-id',required=True)
 args=p.parse_args();project=Project(args.project)
 if args.command=='check':
  with offline_network_guard():
   for f in project.path('configs').glob('*.json'):project.config(str(f.relative_to(project.root)))
   result=verify(project)
  print(json.dumps(result,indent=2));return
 if args.command=='schema-audit':
  with offline_network_guard():
   out=project.output('audits',stamp());result=Schema(project).audit();write(out/'schema_audit.json',result)
  print(out);return
 if args.command=='prepare-study':
  out=project.output('audits',stamp());write(out/'performance_blind_selection.json',prepare_selection(project));print(out);return
 if args.command=='smoke':
  out=project.output('smoke_tests',args.run_id or stamp());os.environ['NLTL_TEST_PROJECT']=str(project.root);os.environ['NLTL_TEST_OUTPUT']=str(out)
  with offline_network_guard():
   suite=unittest.defaultTestLoader.discover(str(project.path('tests')),pattern='test_*.py');stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);out.joinpath('unit_tests.txt').write_text(stream.getvalue())
   if result.wasSuccessful() and not args.skip_core:
    from .evaluation import core_regression
    dest=out/'external_core';dest.mkdir();core=core_regression(project,dest)
   else:core=None
   summary=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),external_core=dict(cases=37,requirements=6,positive=17,negative=20,scope=core['scope']) if core else None,mappings=verify(project),network='Blocked socket creation, DNS and connection; no credentials loaded',output=str(out.relative_to(project.root)))
   write(out/'summary.json',summary);write(out/'schema_audit.json',Schema(project).audit())
  print(stream.getvalue());print(json.dumps(summary,indent=2))
  if not result.wasSuccessful():raise SystemExit(1)
 elif args.command=='run':
  from .runner import Runner
  from .transport import ScriptedTransport,LiveTransport
  cfg=project.config(args.config)
  if cfg['method'] not in ['NLTL','Single-shot']:raise ValueError('Generation requires explicit method config')
  if not args.script and not args.allow_model_calls:raise ValueError('No model calls authorized; supply a local script or explicit live opt-in')
  transport=ScriptedTransport(load(project.path(args.script))) if args.script else LiveTransport(enabled=args.allow_model_calls,project_root=project.root)
  out=project.output('experiments',args.experiment_id)
  if args.script:
   with offline_network_guard():result=Runner(project,cfg,transport,out).run(args.requirement)
  else:result=Runner(project,cfg,transport,out).run(args.requirement)
  print(json.dumps({k:v for k,v in result.items() if k!='history'},indent=2))
 elif args.command=='evaluate-core':
  from .evaluation import core_regression
  out=project.output('smoke_tests',args.run_id or stamp())
  with offline_network_guard():core_regression(project,out)
  print(out)
 elif args.command=='evaluate':
  from .evaluation import evaluate
  out=project.path('outputs/experiments/'+args.experiment_id)
  if not out.is_dir():raise ValueError('Existing experiment required for independent evaluation')
  dest=out/'evaluation';dest.mkdir(exist_ok=False)
  with offline_network_guard():evaluate(project,args.shape_manifest,dest)
  print(dest)
 elif args.command=='analyze-budgets':
  out=project.output('audits',args.experiment_id);write(out/'budget_analysis.json',budget_analysis([load(project.path(x)) for x in args.histories]));print(out)
if __name__=='__main__':main()
