"""Structural SHACL activation/reachability, never a compliance oracle."""
from rdflib import Graph,URIRef,Literal,RDF,RDFS
from rdflib.namespace import SH
from rdflib.collection import Collection
from .core import finding
TARGETS=[SH.targetClass,SH.targetNode,SH.targetSubjectsOf,SH.targetObjectsOf]
LEAVES={SH['class'],SH.datatype,SH.nodeKind,SH.minCount,SH.maxCount,SH.minInclusive,SH.maxInclusive,SH.minExclusive,SH.maxExclusive,SH.hasValue,SH['in'],SH.pattern,SH.minLength,SH.maxLength,SH.languageIn,SH.uniqueLang,SH.equals,SH.disjoint,SH.lessThan,SH.lessThanOrEquals,SH.closed,SH.qualifiedMinCount,SH.qualifiedMaxCount,SH.select,SH.ask}
def deactivated(g,n):return any(isinstance(x,Literal) and x.toPython() is True for x in g.objects(n,SH.deactivated))
def analyze(g):
 roots=set(s for p in TARGETS for s in g.subjects(p,None));roots|={s for s in g.subjects(RDF.type,SH.NodeShape) if (s,RDF.type,RDFS.Class) in g}
 reachable=set();leaves=set();disabled=[];queue=list(roots)
 while queue:
  n=queue.pop()
  if n in reachable:continue
  reachable.add(n)
  if deactivated(g,n):disabled.append(str(n));continue
  operative=False
  for p,o in g.predicate_objects(n):
   if p not in LEAVES:continue
   if p==SH.closed and isinstance(o,Literal) and o.toPython() is False:continue
   if p in [SH.minCount,SH.qualifiedMinCount] and isinstance(o,Literal):
    try:
     if int(o)==0:continue
    except Exception:pass
   operative=True
  # Logical false constraints are valid enforcement; do not reject all empty/nested forms.
  if any(g.objects(n,SH['not'])) or any(h==RDF.nil for p in [SH['or'],SH.xone] for h in g.objects(n,p)):operative=True
  if operative:leaves.add(n)
  for p in [SH.property,SH.node,SH['not'],SH.qualifiedValueShape,SH.sparql]:queue.extend(g.objects(n,p))
  for p in [SH['or'],SH['and'],SH.xone]:
   for head in g.objects(n,p):
    try:queue.extend(Collection(g,head))
    except Exception:pass
 meaningful=set(s for p in LEAVES for s in g.subjects(p,None))
 return dict(roots=sorted(map(str,roots)),reachable=sorted(map(str,reachable)),enforcing_nodes=sorted(map(str,leaves)),deactivated_reachable=disabled,orphan_constraint_nodes=sorted(map(str,meaningful-reachable)),unsupported_custom_targets=sorted(map(str,g.subjects(SH.target,None))),supported=bool(roots and leaves and not disabled))
def checks(c,g):
 result=analyze(g);out=[]
 if not result['roots'] or not result['enforcing_nodes']:
  reason='No supported root activation' if not result['roots'] else 'No active constraints reachable from submitted targets'
  out.append(finding(c,'ACTIVATION_ERROR',reason,'',expected='A source-supported activation route with reachable active constraints',evidence='SHACL core target/shape-reference semantics; '+str(result),suggestion='Establish the correct target/application from source and representation evidence; activate and reference the intended constraints. Do not invent a target or target every nested shape.',location='submitted graph activation',contract_id='SHACL-activation',obligation_id='non-vacuous-root',check_id='activation.root'))
 if result['deactivated_reachable']:
  out.append(finding(c,'UNRESOLVED_CONTEXT','Reachable enforcement is deactivated','',expected='Source-grounded justification of deactivation before acceptance',evidence=str(result),suggestion='Resolve the intended active scope against source; do not silently disable obligations.',location='sh:deactivated',confirmed=False,assessment='MATERIAL_ACTIVATION_UNCERTAINTY'))
 if result['unsupported_custom_targets']:
  out.append(finding(c,'UNRESOLVED_CONTEXT','Custom SHACL target is outside supported activation analysis','',expected='Supported target or an explicitly reviewed execution extension',evidence=str(result),suggestion='Resolve custom target execution support and applicability without guessing.',location='sh:target',confirmed=False,assessment='UNSUPPORTED_ACTIVATION'))
 return out
