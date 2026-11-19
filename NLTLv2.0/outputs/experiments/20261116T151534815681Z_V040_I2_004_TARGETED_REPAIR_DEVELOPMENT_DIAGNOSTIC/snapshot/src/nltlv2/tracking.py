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
 def __init__(self):self.catalog={};self.attempts=[];self.witness_observations={}
 def observe(self,c,findings,coverage,*,static_complete=True,review_complete=False,runtime_complete=False):
  if any(f.version!=c.version or f.candidate_sha256!=c.sha256 for f in findings):raise ValueError('STALE_TRACKING_FINDING')
  current={f.key:f for f in findings};prior=set(self.catalog);changes={k:[] for k in ['new','resolved','persistent','regressed','unassessable']};details=[]
  witnesses={(w.get('contract_scope_id'),w.get('obligation_id'),w['witness_id']):w['status'] for w in coverage.get('witnesses',[])}
  for key in sorted(prior|set(current)):
   f=current.get(key);entry=self.catalog.get(key)
   if entry is None:
    entry=dict(identity=dict(contract_id=f.contract_id,obligation_id=f.obligation_id,witness_id=f.witness_id,check_id=f.check_id),first_seen=c.version,last_assessable_failure=False,ever_failed=False,assessment=f.assessment,location=f.location,query_sha256=f.query_sha256,blocking=f.blocking);self.catalog[key]=entry
   if f is not None:
    observed_before=self.witness_observations.get((f.contract_id,f.obligation_id,f.witness_id)) if f.witness_id else None
    state='REGRESSED' if (entry['ever_failed'] and not entry['last_assessable_failure']) or observed_before=='OBSERVED_MATCH' else 'PERSISTENT' if key in prior else 'NEW'
    entry.update(last_assessable_failure=True,ever_failed=True,assessment=f.assessment,location=f.location,query_sha256=f.query_sha256,blocking=f.blocking)
   else:
    identity=entry['identity'];status=witnesses.get((identity['contract_id'],identity['obligation_id'],identity['witness_id']))
    if identity['witness_id']:
     if status=='OBSERVED_MATCH':state='RESOLVED';entry['last_assessable_failure']=False
     elif status=='CONFIRMED_COUNTEREXAMPLE':state='PERSISTENT' # A missing emission is not resolution.
     else:state='UNASSESSABLE'
    elif entry['assessment']=='CONFIRMED_CANDIDATE_QUERY_ERROR':
     execution_known=runtime_complete or (coverage.get('witnesses') and all(w['status'] in ['OBSERVED_MATCH','CONFIRMED_COUNTEREXAMPLE'] for w in coverage['witnesses']))
     state='RESOLVED' if execution_known else 'UNASSESSABLE'
     if state=='RESOLVED':entry['last_assessable_failure']=False
    elif entry['assessment']=='REGRESSION_GUARD':
     from .checks import obligation_signature
     import json
     original=entry['guard_finding'];required={tuple(x) for x in json.loads(original.diagnostic.split('REMOVED_OR_CHANGED ',1)[1])}
     state='RESOLVED' if required<=obligation_signature(c.code) else 'UNASSESSABLE'
     if state=='RESOLVED':entry['last_assessable_failure']=False
    elif entry.get('semantic_review'):
     state='RESOLVED' if review_complete else 'UNASSESSABLE'
     if state=='RESOLVED':entry['last_assessable_failure']=False
    else:
     state='RESOLVED' if static_complete else 'UNASSESSABLE'
     if state=='RESOLVED':entry['last_assessable_failure']=False
   if f is not None:
    entry['last_finding_version']=c.version;entry['last_finding_candidate_sha256']=c.sha256
    entry['semantic_review']=f.location.startswith('semantic reviewer')
    if f.assessment=='REGRESSION_GUARD':entry['guard_finding']=f
   entry.update(state=state,last_seen=c.version,candidate_sha256=c.sha256)
   changes[state.lower()].append(key);details.append(dict(key=key,state=state,**entry['identity'],location=entry['location'],query_sha256=entry['query_sha256'],location_version=entry.get('last_finding_version'),location_candidate_sha256=entry.get('last_finding_candidate_sha256'),location_is_current=f is not None,candidate_version=c.version,candidate_sha256=c.sha256,blocking=entry['blocking']))
  for identity,observed in witnesses.items():
   if observed in ['OBSERVED_MATCH','CONFIRMED_COUNTEREXAMPLE']:self.witness_observations[identity]=observed
  failures=sorted(f.key for f in findings if f.assessment=='DEMONSTRATED_BEHAVIORAL_FAILURE')
  fingerprint=structural_fingerprint(c.code);previous=self.attempts[-1] if self.attempts else None
  repeated=bool(failures and previous and failures==previous['behavioral_failure_ids'])
  exact=bool(previous and previous['sha256']==c.sha256);equivalent=bool(previous and previous['structural_fingerprint']==fingerprint)
  older=[a['version'] for a in self.attempts[:-1] if a['structural_fingerprint']==fingerprint]
  oscillation=bool(older and not equivalent)
  row=dict(version=c.version,sha256=c.sha256,structural_fingerprint=fingerprint,behavioral_failure_ids=failures,unchanged_candidate=exact,structurally_equivalent_to_previous=equivalent,oscillation=oscillation,returns_to_versions=older,repeated_behavioral_failure_set=repeated,consecutive_same_failure_set=(previous['consecutive_same_failure_set']+1 if repeated else 1 if failures else 0),consecutive_unchanged=(previous['consecutive_unchanged']+1 if exact else 0))
  self.attempts.append(row)
  summary=dict(current_version=c.version,full_attempt_budget_unchanged=True,repeat_detection=row,persistent_or_regressed=[d for d in details if d['state'] in ['PERSISTENT','REGRESSED']],unassessable=[d for d in details if d['state']=='UNASSESSABLE'],instruction='Repeated observations remain failures despite query edits. Diagnose binding/branch structure from current evidence instead of cycling previous code. Unassessable means no evidence of resolution.')
  return dict(**changes,details=details),summary
 def carry_unrestored_guards(self,c,current_findings):
  from .checks import obligation_signature
  import json
  emitted={f.key for f in current_findings};out=[];signature=obligation_signature(c.code)
  for key,entry in self.catalog.items():
   old=entry.get('guard_finding')
   if old is None or key in emitted:continue
   required={tuple(x) for x in json.loads(old.diagnostic.split('REMOVED_OR_CHANGED ',1)[1])}
   if required<=signature:continue
   out.append(finding(c,'SOURCE_BACKED_LOGIC_ERROR','Previously removed obligation is still unrestored','',expected=old.expected,evidence=old.evidence,suggestion='Restore the recorded prior obligation or obtain an explicit evidence-backed adjudication; another query edit is not resolution.',location='insertion context: prior obligation preservation',diagnostic=old.diagnostic,contract_id=old.contract_id,obligation_id=old.obligation_id,check_id=old.check_id,assessment='REGRESSION_GUARD'))
  return out
 def stagnation_stop(self,policy):
  if not policy.get('enabled',False) or not self.attempts:return None
  row=self.attempts[-1]
  for kind,value in [('repeated_failure_set_limit',row['consecutive_same_failure_set']),('unchanged_candidate_limit',row['consecutive_unchanged']),('oscillation_limit',sum(a['oscillation'] for a in self.attempts))]:
   limit=policy.get(kind)
   if limit is not None and value>=limit:return kind+'='+str(limit)
  return None
