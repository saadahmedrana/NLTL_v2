from __future__ import annotations
import argparse,json,unittest,io,os,sys,subprocess,hashlib
from .core import Project,write,load,stamp,offline_network_guard
from .schema import Schema

def main():
 p=argparse.ArgumentParser();p.add_argument('--project',default='.');sub=p.add_subparsers(dest='command',required=True)
 sub.add_parser('check');sub.add_parser('schema-audit')
 s=sub.add_parser('smoke');s.add_argument('--run-id');s.add_argument('--skip-core',action='store_true')
 e=sub.add_parser('evaluate-core');e.add_argument('--run-id')
 g=sub.add_parser('run');g.add_argument('--config',required=True);g.add_argument('--requirement',required=True);g.add_argument('--experiment-id',required=True);g.add_argument('--script');g.add_argument('--allow-model-calls',action='store_true')
 a=sub.add_parser('analyze-budgets');a.add_argument('histories',nargs='+');a.add_argument('--run-id')
 args=p.parse_args();project=Project(args.project)
 if args.command in ['check','schema-audit']:
  with offline_network_guard():
   for f in project.path('configs').glob('*.json'):project.config(str(f.relative_to(project.root)))
   result=Schema(project).audit()
   lock=project.path('schema/runtime_lock.json')
   if lock.exists():
    for name,h in load(lock)['files'].items():
     if hashlib.sha256(project.path(name).read_bytes()).hexdigest()!=h:raise ValueError('Runtime lock mismatch '+name)
  print(json.dumps(result,indent=2));return
 if args.command=='run':
  from .runner import Runner
  from .transport import ScriptedTransport,LiveTransport
  cfg=project.config(args.config)
  if cfg['method'] not in ['NLTL','Single-shot']:raise ValueError('Explicit generation workflow required')
  if not args.script and not args.allow_model_calls:raise ValueError('No model calls authorized')
  transport=ScriptedTransport(load(project.path(args.script))) if args.script else LiveTransport(enabled=args.allow_model_calls,project_root=project.root)
  out=project.output('experiments',args.experiment_id)
  if args.script:
   with offline_network_guard():result=Runner(project,cfg,transport,out).run(args.requirement)
  else:result=Runner(project,cfg,transport,out).run(args.requirement)
  print(json.dumps({k:v for k,v in result.items() if k!='history'},indent=2));return
 if args.command=='analyze-budgets':
  from .study import budget_analysis
  out=project.output('audits',args.run_id or stamp());write(out/'budget_analysis.json',budget_analysis([load(project.path(x)) for x in args.histories]));print(out);return
 out=project.output('smoke_tests',args.run_id or stamp())
 if args.command=='smoke':
  os.environ['NLTL_TEST_PROJECT']=str(project.root);os.environ['NLTL_TEST_OUTPUT']=str(out)
  with offline_network_guard():
   suite=unittest.defaultTestLoader.discover(str(project.path('tests')),pattern='test_*.py');stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite);(out/'unit_tests.txt').write_text(stream.getvalue())
  print(stream.getvalue());summary=dict(version='0.6.0',tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),model_calls=0,network='BLOCKED',external_core=None)
  write(out/'summary.json',summary)
  if not result.wasSuccessful():raise SystemExit(1)
 else:summary=dict(version='0.6.0',model_calls=0)
 if args.command=='evaluate-core' or not args.skip_core:
  # Separate process, after production tests finish. No evaluation imports in Runner.
  dest=str(out.relative_to(project.root)/'external_core');env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
  process=subprocess.run([sys.executable,str(project.path('evaluation/run_reference_controls.py')),'--project',str(project.root),'--output',dest],env=env,capture_output=True,text=True)
  (out/'external_evaluation_stdout.txt').write_text(process.stdout);(out/'external_evaluation_stderr.txt').write_text(process.stderr)
  if process.returncode:raise RuntimeError('Independent reference evaluation failed: '+process.stderr)
  summary['external_core']=dict(cases=37,positive=17,negative=20,counterparts=20,scope='Independent source-authored reference controls, not generated workflow accuracy')
 write(out/'summary.json',summary);print(json.dumps(dict(summary,output=str(out)),indent=2))
if __name__=='__main__':main()
