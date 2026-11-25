from pathlib import Path
import json,hashlib
from rdflib import Graph,Namespace,RDF
from rdflib.namespace import SH
from nltlv2.core import offline_network_guard,write
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');state=json.loads(Path('/private/tmp/v070_i2004_operational_state.json').read_text());g=Path(state['group']);assert (g/'dispatch_closed.json').exists();shape=Graph().parse(g/'I2-004/nltl/candidate_01.ttl');cases=json.loads((g/'evaluation/selection.json').read_text())['cases'];n=Namespace('https://w3id.org/nltl/vocab#');rows=[]
with offline_network_guard():
 for source,q in shape.subject_objects(SH.sparql):
  query=str(shape.value(q,SH.select));qh=hashlib.sha256(query.encode()).hexdigest()
  for c in [x for x in cases if x['expected']=='PASS']:
   data=Graph().parse(R/c['fixture']);ships=list(data.subjects(RDF.type,n.ship));assert len(ships)==1
   try:result=[{str(k):str(v) for k,v in row.asdict().items()} for row in data.query(query,initBindings={'this':ships[0]})];error=None
   except Exception as e:result=[];error=type(e).__name__+': '+str(e)
   rows.append(dict(source_shape=str(source),query_sha256=qh,exact_original_query=query,case_id=c['case_id'],bindings={'this':str(ships[0])},rows=result,error=error,scope='Read-only execution of exact saved SELECT text, after dispatch; no shape edits, no effect on actual deactivated SHACL verdict or workflow selection.'))
write(g/'evaluation/query_branch_diagnostics.json',rows);print(json.dumps([dict(case_id=x['case_id'],query=x['query_sha256'][:10],rows=len(x['rows']),error=x['error']) for x in rows],indent=2))
