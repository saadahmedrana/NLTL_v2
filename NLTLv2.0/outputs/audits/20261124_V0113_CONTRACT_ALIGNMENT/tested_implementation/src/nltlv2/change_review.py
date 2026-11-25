"""General structural change accounting. This never certifies a regulatory fix."""
import difflib
from rdflib import Graph,RDFS
from rdflib.namespace import SH
from rdflib.compare import to_isomorphic,graph_diff
from .core import digest
COSMETIC={SH.message,SH.name,SH.description,RDFS.label,RDFS.comment}
def manifest(previous,current):
 out=dict(previous_version=previous.version,previous_sha256=previous.sha256,current_version=current.version,current_sha256=current.sha256,diff=''.join(difflib.unified_diff(previous.code.splitlines(True),current.code.splitlines(True),fromfile='v'+str(previous.version),tofile='v'+str(current.version))),changes=[],policy='Every functional change requires source-grounded model review; no pre-issued or per-requirement change permissions. Model support is an interpretation, not independently verified truth.')
 try:a=Graph().parse(data=previous.code,format='turtle');b=Graph().parse(data=current.code,format='turtle')
 except Exception as e:return dict(out,status='PREVIOUS_OR_CURRENT_PARSE_UNASSESSABLE',diagnostic=str(e))
 for g in [a,b]:
  for p in COSMETIC:g.remove((None,p,None))
 same,removed,added=graph_diff(to_isomorphic(a),to_isomorphic(b));groups={}
 def group(p):
  if p in [SH.select,SH.ask,SH.sparql]:return 'QUERY'
  if p in [SH.targetClass,SH.targetNode,SH.targetSubjectsOf,SH.targetObjectsOf,SH.deactivated]:return 'TARGET_APPLICABILITY'
  if p in [SH.datatype,SH.nodeKind]:return 'TYPE'
  if p in [SH.minCount,SH.maxCount,SH.minInclusive,SH.maxInclusive,SH.minExclusive,SH.maxExclusive,SH.hasValue,SH['in']]:return 'VALUE_CARDINALITY'
  return 'PATH_LOGIC_STRUCTURE'
 for label,g in [('removed',removed),('added',added)]:
  for s,p,o in g:groups.setdefault(group(p),{'removed':[],'added':[]})[label].append(s.n3()+' '+p.n3()+' '+o.n3()+' .')
 for kind,values in sorted(groups.items()):
  for k in values:values[k].sort()
  alerts=[dict(alert_id=digest(kind+'removal'+str(values['removed'])),kind=kind,removed_triples=values['removed'],reason='Removed functional constraints/operands. Explicitly assess numeric/unit/query loss and any replacement against source, not against a handwritten solution.') ] if values['removed'] else []
  out['changes'].append(dict(change_id=digest(kind+str(values)),kind=kind,removal_alerts=alerts,**values))
 return dict(out,status='STRUCTURAL_CHANGES_RECORDED',isomorphic_functional_graph=not out['changes'],note='Blank-node graph alignment can group surrounding structure; inspect full code and textual diff. No equivalence or regression claim is inferred from this diff alone.')
