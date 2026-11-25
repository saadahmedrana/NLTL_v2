"""Bookkeeping for serial invocations of the existing runner; no model/evaluation route."""
import pathlib,json,sys,time
A=pathlib.Path(__file__).resolve().parent;R=A.parents[2];master=pathlib.Path(sys.argv[1]);cfg=json.loads((A/'experiment.dispatch.json').read_text());rows=[];closed=True;calls=0
for j in cfg['jobs']:
 d=R/'outputs/experiments'/j['run_id'];row=dict(model=j['model'],requirement_id=j['requirement_id'],run_id=j['run_id'],status='NOT_RUN',reason='Not started before frozen terminal/time stop')
 if d.exists():
  f=d/'dispatch_closed.json'
  if f.exists():
   c=json.loads(f.read_text());ok=c.get('dispatch_closed') is True and c.get('outstanding_provider_processes')==0;closed&=ok;row.update(status='CLOSED' if ok else 'INCOMPLETE',physical_calls=c['physical_calls'],errors=c['errors']);calls+=c['physical_calls']
  else:row.update(status='ERROR',reason='Started output has no dispatch-closure receipt');closed=False
 rows.append(row)
receipt=dict(label='FROZEN_20_10_DEVELOPMENT_QUEUE',all_started_dispatches_closed=closed,physical_calls=calls,max_physical_calls=330,queue=rows,not_run=sum(r['status']=='NOT_RUN' for r in rows),closed=sum(r['status']=='CLOSED' for r in rows),planned_pairs=30,generated_performance_consulted=False)
(master/'queue_status.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(done=receipt['closed'],not_run=receipt['not_run'],in_progress=0,physical_calls=calls,all_started_dispatches_closed=closed)),flush=True)
