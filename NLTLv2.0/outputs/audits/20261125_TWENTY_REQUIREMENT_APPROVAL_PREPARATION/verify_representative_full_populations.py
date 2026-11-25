from pathlib import Path
import json,sys,time
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Project,write,offline_network_guard
from nltlv2.schema import Schema
from nltlv2.evidence import literal_identity
from rdflib import Graph,RDF,URIRef
from owlrl import DeductiveClosure,RDFS_Semantics
load=lambda p:json.loads(p.read_text());s=Schema(Project(R));selection=load(A/'selection.frozen.json');bm=load(A/'evaluation_bindings_manifest.json');rows=[]
with offline_network_guard():
 for rid in ['I2-046','TRF-036','TRF-050']:
  proof=next(p for p in bm['construction_proofs'] if p['requirement_id']==rid);scope=R/selection['scope_files'][rid];decl=load(scope if scope.exists() else Path(str(scope).replace('.approved.','.proposed.')));g=Graph()
  with literal_identity():data=Graph().parse(R/proof['file'])
  for t in s.graph:g.add(t)
  for t in data:g.add(t)
  start=time.monotonic();DeductiveClosure(RDFS_Semantics).expand(g);nodes=sorted(str(n) for n in g.subjects(RDF.type,URIRef(decl['focus_set']['owner_class'])));assert nodes==load(R/proof['binding_file'])['admitted_nodes'];rows.append(dict(requirement_id=rid,status='FULL_SCHEMA_RDFS_POPULATION_MATCH',elapsed_seconds=time.monotonic()-start,scope_approval='PENDING_NOT_SIMULATED'));print(rid,'FULL_POPULATION_MATCH',flush=True)
write(A/'representative_full_population_checks.json',rows)
