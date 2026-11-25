"""Evidence-aware finding reconciliation and explicitly configured stagnation policy."""
from rdflib import Graph,Variable,Literal
from rdflib.compare import to_isomorphic
from .core import digest,finding
from rdflib.namespace import SH
from rdflib.plugins.sparql.parser import parseQuery
from .sparql_analysis import children

def canonical_query(query):
 # Structural repeat detection only, not an equivalence proof. Alpha-normalize
 # EXISTS-local variables separately, preserving externally visible bindings.
 import json
 from rdflib.plugins.sparql.parserutils import CompValue
 tree=parseQuery(query)
 def exposed(x):
  if isinstance(x,Variable):return [str(x)]
  if isinstance(x,CompValue) and x.name in ['Builtin_EXISTS','Builtin_NOTEXISTS']:return []
  return [name for _,v in children(x) for name in exposed(v)]
 outer=list(dict.fromkeys(exposed(tree)));mapping={'this':'this'}
 for name in outer:
  if name not in mapping:mapping[name]='g'+str(len(mapping))
 def encode(x,scope,visible):
  if isinstance(x,Variable):return ['var',scope.setdefault(str(x),'g'+str(len(scope)))]
  if isinstance(x,CompValue):
   if x.name in ['Builtin_EXISTS','Builtin_NOTEXISTS']:
    graph=x.get('graph');local=list(dict.fromkeys(exposed(graph)));child=dict(scope)
    for name in local:
     if name not in visible:child[name]='local'+str(sum(v.startswith('local') for v in child.values()))
    return [x.name,encode(graph,child,visible|set(local))]
   return [x.name,[[str(k),encode(v,scope,visible)] for k,v in children(x)]]
  if children(x):return [encode(v,scope,visible) for _,v in children(x)]
  return x.n3() if callable(getattr(x,'n3',None)) else str(x)
 return json.dumps(encode(tree,mapping,set(outer)),sort_keys=True)
def structural_fingerprint(code):
 try:
  graph=Graph().parse(data=code,format='turtle')
  for subject,query in list(graph.subject_objects(SH.select)):
   graph.set((subject,SH.select,Literal(canonical_query(str(query)))))
  return str(to_isomorphic(graph).graph_digest())
 except Exception:return digest(code)

class Tracker:
 def __init__(self):self.catalog={};self.attempts=[]
 def prior_semantic_issues(self):
  return [dict(issue_id=e['finding'].obligation_id,last_seen_version=e['finding'].version,last_seen_sha256=e['finding'].candidate_sha256,finding=e['finding'].asdict()) for e in self.catalog.values() if e['finding'].assessment in ['MODEL_INTERPRETATION','UNRESOLVED_CONTEXT'] and e['state']!='RESOLVED']
 def observe(self,c,findings,*,static_complete=True,review=None,runtime_complete=False):
  if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_TRACKING_FINDING')
  current={f.key:f for f in findings};changes={k:[] for k in ['new','resolved','persistent','regressed','unassessable']};details=[]
  reconciled={x['issue_id']:x['state'] for x in (review or {}).get('reconciliations',[])}
  for key in sorted(set(self.catalog)|set(current)):
   f=current.get(key);entry=self.catalog.get(key)
   if f:
    state='NEW' if not entry else 'REGRESSED' if entry['state']=='RESOLVED' else 'PERSISTENT';entry=dict(finding=f,state=state)
   else:
    old=entry['finding']
    if old.assessment in ['MODEL_INTERPRETATION','UNRESOLVED_CONTEXT']:state=reconciled.get(old.obligation_id,'UNASSESSABLE')
    elif old.assessment=='CONFIRMED_CANDIDATE_QUERY_ERROR':state='RESOLVED' if runtime_complete else 'UNASSESSABLE'
    else:state='RESOLVED' if static_complete else 'UNASSESSABLE'
    entry['state']=state
   self.catalog[key]=entry;changes[state.lower()].append(key);old=entry['finding']
   details.append(dict(key=key,state=state,issue_id=old.obligation_id,assessment=old.assessment,location=old.location,location_version=old.version,location_candidate_sha256=old.candidate_sha256,location_is_current=f is not None,current_version=c.version,current_sha256=c.sha256,model_resolution_is_not_independent_proof=old.assessment in ['MODEL_INTERPRETATION','UNRESOLVED_CONTEXT']))
  failures=sorted(f.key for f in findings if f.blocking);previous=self.attempts[-1] if self.attempts else None;fingerprint=structural_fingerprint(c.code)
  repeat=bool(previous and failures and previous['failure_ids']==failures);exact=bool(previous and previous['sha256']==c.sha256);older=[a['version'] for a in self.attempts[:-1] if a['structural_fingerprint']==fingerprint]
  row=dict(version=c.version,sha256=c.sha256,structural_fingerprint=fingerprint,failure_ids=failures,unchanged_candidate=exact,oscillation=bool(older and previous['structural_fingerprint']!=fingerprint),returns_to_versions=older,consecutive_same_failure_set=previous['consecutive_same_failure_set']+1 if repeat else 1 if failures else 0,consecutive_unchanged=previous['consecutive_unchanged']+1 if exact else 0)
  self.attempts.append(row)
  return dict(**changes,details=details),dict(current_version=c.version,current_sha256=c.sha256,repeat_detection=row,persistent_or_regressed=[x for x in details if x['state'] in ['PERSISTENT','REGRESSED']],unassessable=[x for x in details if x['state']=='UNASSESSABLE'],instruction='A query edit or missing review is not resolution. Semantic resolution requires an explicit source-grounded reviewer reconciliation and remains a model interpretation.')
 def stagnation_stop(self,policy):
  if not policy.get('enabled',False) or not self.attempts:return None
  row=self.attempts[-1]
  for kind,value in [('repeated_failure_set_limit',row['consecutive_same_failure_set']),('unchanged_candidate_limit',row['consecutive_unchanged']),('oscillation_limit',sum(a['oscillation'] for a in self.attempts))]:
   if policy.get(kind) is not None and value>=policy[kind]:return kind+'='+str(policy[kind])
  return None
