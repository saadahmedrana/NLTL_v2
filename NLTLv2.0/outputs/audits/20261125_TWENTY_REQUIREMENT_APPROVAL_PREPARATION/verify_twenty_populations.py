from pathlib import Path
import sys,json,importlib.util,hashlib,time
R=Path('/Users/sadisfaction570/Desktop/Journal 1/NLTL_v2/NLTLv2.0');A=R/'outputs/audits/20261125_TWENTY_REQUIREMENT_APPROVAL_PREPARATION';sys.path.insert(0,str(R/'src'))
from nltlv2.core import Project,write,offline_network_guard
from nltlv2.schema import Schema,N
from nltlv2.evidence import literal_identity
from rdflib import Graph,RDF,RDFS,URIRef
from owlrl import DeductiveClosure,RDFS_Semantics
spec=importlib.util.spec_from_file_location('expanded_pop',R/'evaluation/expanded_development.py');ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)
load=lambda p:json.loads(p.read_text());s=Schema(Project(R));bm=load(A/'evaluation_bindings_manifest.json');sel=load(A/'selection.frozen.json');defs=load(A/'scope_definition_hashes.json');rows=[];start=time.monotonic()
with offline_network_guard():
 base=Graph()
 for t in s.graph:base.add(t)
 DeductiveClosure(RDFS_Semantics).expand(base)
 owners={URIRef((load(R/f.replace('.approved.','.proposed.')) if not (R/f).exists() else load(R/f))['focus_set']['owner_class']) for f in sel['scope_files'].values()}
 assert not [(str(o),str(n)) for o in owners for n in base.subjects(RDF.type,o)],'Schema independently contributes declared population nodes'
 # Fixtures are ordinary assertion graphs, not additional RDFS axiom programs.
 for proof in bm['construction_proofs']:
  with literal_identity():g=Graph().parse(R/proof['file'])
  assert not any(p in [RDFS.subClassOf,RDFS.subPropertyOf,RDFS.domain,RDFS.range] for _,p,_ in g)
  rid=proof['requirement_id'];f=sel['scope_files'][rid];decl=load(R/f if (R/f).exists() else R/f.replace('.approved.','.proposed.'));owner=URIRef(decl['focus_set']['owner_class']);nodes=sorted(str(n) for n in ex.representation_graph(g,s.graph).subjects(RDF.type,owner));binding=load(R/proof['binding_file']);assert nodes==binding['admitted_nodes']
  rows.append(dict(file=proof['file'],population_matches=True,admitted_nodes=len(nodes)))
 write(A/'population_derivation_verification.json',dict(status='PASS',files=len(rows),rows=rows,schema_owner_instances_absent=True,fixtures_have_no_new_rdfs_axioms=True,method='Relevant original-assertion RDFS domain/range/subproperty/subclass closure. Existing full-schema population bindings independently agree where previously computed. Actual approved-boundary validate_data_scope remains mandatory in independent evaluation.',elapsed_seconds=time.monotonic()-start))
print('POPULATION_DERIVATION_PASS',len(rows),flush=True)
