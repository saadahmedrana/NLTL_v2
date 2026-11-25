import pathlib,json,sys
R=pathlib.Path(__file__).resolve().parents[3];d=R/'outputs/experiments'/sys.argv[1];r=json.loads((d/'dispatch_closed.json').read_text());assert r['dispatch_closed'] is True and r['outstanding_provider_processes']==0
bad=bool(r['errors']);states={}
for arm in ['Single-shot','NLTL']:
 p=d/sys.argv[2]/arm/'run.json';v=json.loads(p.read_text()) if p.exists() else {};states[arm]=v.get('status','MISSING_OUTPUT');bad|=states[arm] in ['INFRASTRUCTURE_FAILURE','REQUEST_INTEGRITY_FAILURE','RESOURCE_ATTRIBUTION_UNCERTAIN','MISSING_OUTPUT']
print(json.dumps(dict(run_id=sys.argv[1],calls=r['physical_calls'],terminal_states=states,stop_remaining=bad)),flush=True)
raise SystemExit(2 if bad else 0)
