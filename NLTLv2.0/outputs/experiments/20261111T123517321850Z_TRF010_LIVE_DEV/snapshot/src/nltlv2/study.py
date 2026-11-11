from __future__ import annotations
import collections,random,json
from .core import load,write,digest

def prepare_selection(project,seed=20261111):
 # Deliberately load no workflow outcomes, score columns or generated code.
 reqs=load(project.path('data/requirements/requirements.json'));index=load(project.path('data/contracts/requirement_term_index.json'));core=load(project.path('evaluation/selections/regression_core.json'))
 buckets=collections.defaultdict(list)
 for rid,req in sorted(reqs.items()):
  c=index['dependencyContracts'].get(rid,{})
  branches=len(c.get('selectorPolicies',[]))+bool(c.get('applicabilityTerms'))+bool(c.get('tableModel'))
  complexity='high' if c.get('tableModel') or len(c.get('modelPaths',[]))>1 else 'medium' if c.get('formulaExpression') or branches else 'low'
  buckets[(rid.split('-')[0],c.get('verificationMode','UNRESOLVED'),str(branches),complexity)].append(rid)
 rng=random.Random(seed)
 for vals in buckets.values():rng.shuffle(vals)
 order=[]
 while any(buckets.values()):
  for key in sorted(buckets):
   if buckets[key]:order.append(buckets[key].pop())
 queue=order[:50];ready=core['requirements']
 return dict(status='PREPARED_NOT_RUN_REVIEW_GATE_CLOSED',seed=seed,selection_inputs='requirement/source + verification mode + represented branch indicators + structural complexity only',review_queue_50=queue,ready_development_requirements=ready,ready_count=len(ready),gap_to_50=50-len(ready),policy='Queue is not certified. Review all positives/negatives and branches before final selection. Six existing core requirements are eligible development evidence only; no manufactured 50-requirement benchmark.',config='configs/iteration_study.json')

def budget_analysis(histories,budgets=(2,3,4,5,6)):
 out=[]
 for run in histories:
  for b in budgets:
   prefix=[h for h in run['history'] if h['attempt']<=b];selected=next((h for h in prefix if h.get('accepted')),None)
   out.append(dict(requirement_id=run['requirement_id'],budget=b,selected_version=selected['version'] if selected else None,status='ACCEPTED' if selected else 'NO_VERDICT',request_metrics=[m for h in prefix for m in h.get('request_metrics',[])],runtime_seconds=sum(m.get('elapsed_seconds',0) for h in prefix for m in h.get('request_metrics',[])),input_tokens=sum(m.get('usage',{}).get('input_tokens',0) for h in prefix for m in h.get('request_metrics',[])),output_tokens=sum(m.get('usage',{}).get('output_tokens',0) for h in prefix for m in h.get('request_metrics',[])),acceptance_attempt=selected['attempt'] if selected else None,regressions=sum(any(f.get('location')=='repair regression guard' for f in h.get('findings',[])) for h in prefix),selection_rule='First internally accepted candidate only',history_prefix=prefix))
 return out
