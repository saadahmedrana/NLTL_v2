"""Saved-history budget accounting only; no study selection or dispatch."""
def budget_analysis(histories,budgets=(2,3,4,5,6)):
 out=[]
 for run in histories:
  for b in budgets:
   prefix=[h for h in run['history'] if h['attempt']<=b];selected=next((h for h in prefix if h.get('accepted')),None)
   out.append(dict(requirement_id=run['requirement_id'],budget=b,selected_version=selected['version'] if selected else None,status='ACCEPTED' if selected else 'NO_VERDICT',request_metrics=[m for h in prefix for m in h.get('request_metrics',[])],runtime_seconds=sum(h.get('elapsed_seconds',0) for h in prefix),provider_seconds=sum(m.get('elapsed_seconds',0) for h in prefix for m in h.get('request_metrics',[])),input_tokens=sum(m.get('usage',{}).get('input_tokens',0) for h in prefix for m in h.get('request_metrics',[])),output_tokens=sum(m.get('usage',{}).get('output_tokens',0) for h in prefix for m in h.get('request_metrics',[])),acceptance_attempt=selected['attempt'] if selected else None,regressions=sum(any(f.get('location')=='repair regression guard' for f in h.get('findings',[])) for h in prefix),selection_rule='First internally accepted candidate only',history_prefix=prefix))
 return out
