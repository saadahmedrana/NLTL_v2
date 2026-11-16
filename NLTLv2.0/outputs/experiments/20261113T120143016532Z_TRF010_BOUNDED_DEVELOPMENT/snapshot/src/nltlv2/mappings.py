import json,collections,hashlib
from .core import load

def verify(project):
 from .schema import Schema
 Schema(project).validate_enumeration_contracts()
 reqs=load(project.path('mappings/requirements.json'));cases=load(project.path('mappings/cases.json'));known={x['requirement_id'] for x in reqs}
 for rows,key in [(reqs,'requirement_id'),(cases,'case_id')]:
  ids=[x[key] for x in rows]
  if len(ids)!=len(set(ids)):raise ValueError('Duplicate '+key)
 for row in cases:
  if row['requirement_id'] not in known:raise ValueError('Broken requirement reference')
  for key in ['fixture','counterfactual']:
   if row[key] and not project.path(row[key]).is_file():raise ValueError('Broken '+key)
 for row in reqs:
  for key in ['requirement_reference','schema','contract']:
   value=row[key];file,_,pointer=value.partition('#');data=project.path(file)
   if not data.is_file():raise ValueError('Broken mapping reference')
   if pointer:
    obj=load(data)
    for part in pointer.strip('/').split('/'):obj=obj[part]
  for config in row['configs'].split(';'):project.config(config)
 core=load(project.path('evaluation/selections/regression_core.json'))
 for c in core['cases']:
  for k in ['fixture','counterfactual']:
   if c.get(k) and hashlib.sha256(project.path(c[k]).read_bytes()).hexdigest()!=c[k+'_sha256']:raise ValueError('Fixture hash mismatch '+c['case_id'])
 facts=load(project.path('evaluation/selections/snapshot_facts.json'));inv=load(project.path('evaluation/selections/case_inventory.json'));current=[c for c in inv if c['scope']=='CURRENT_157']
 if len(current)!=1290 or sum(c['expected']=='PASS' for c in current)!=606 or sum(c['expected']=='FAIL' for c in current)!=684:raise ValueError('Historical inventory count mismatch')
 snapshot=load(project.path('evaluation/selections/historical_553_case_ids.json'))
 if len(snapshot)!=553 or len({c['requirement_id'] for c in inv if c['case_id'] in snapshot})!=157:raise ValueError('Historical snapshot identity mismatch')
 return dict(requirements=len(reqs),case_inventory=len(cases),snapshot=553,snapshot_requirements=157,core=len(core['cases']),core_requirements=len(core['requirements']),ready_for_50=6,gap=44)
