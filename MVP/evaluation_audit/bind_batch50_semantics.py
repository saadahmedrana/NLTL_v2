"""Bind independently defined defects to explicitly reviewed frozen constraints.

No validation reports are read. Repairs and fixture oracles are not changed.
Fingerprints identify reviewed constraint structure/query, never message text or
blank-node IDs. Unrelated/broken queries are deliberately not admitted.
"""
import hashlib
from pathlib import Path
from rdflib import Graph, RDF
import audit
P=audit.HERE/'reviewed_failure_specs_batch50.json'
BASE=audit.HERE/'outputs/20261108T124921Z'

def bind():
    specs=audit.read(P);rows=audit.read(BASE/'retained_rows.json');records=[]
    for spec in specs[14:]:
        req=spec['requirement'];cid=spec['case']
        frozen_repair=(list(spec['removed_triples']),list(spec['added_triples']),dict(spec['fixture_oracle']))
        for w in audit.WORKFLOWS:
            r=next(r for r in rows if r['condition']==w and r['case_id']==cid)
            g=Graph().parse(BASE/'corrected_benchmark'/r['rdf_path']);ship=next(g.subjects(RDF.type,audit.N.ship))
            focus=ship;component=None;query_selector=None;review=''
            if req=='I2-019' and w=='NO_SEMANTIC':
                focus=g.value(ship,audit.N.hasStructuralMember);component='SPARQLConstraintComponent'
                query_selector='HAVING' if cid.endswith('F01') else 'FILTER NOT EXISTS'
                review='The member-scoped MAX/HAVING comparison checks selected factor against every spanned factor; the other reviewed query checks absent selectedHullAreaFactor. Exact selected query is bound, not every SPARQL query on the node.'
            elif req=='TRF-003':
                component='OrConstraintComponent';review='The 2015 date selects the 2012<=date<2019 branch, requiring edition 2010. Other date branches are inapplicable. This case predates the earlier-date exception.'
            elif req=='I2-006' and w=='SINGLESHOT' and cid.endswith(('F02','F03')):
                component='OrConstraintComponent';review='With astern intent true, the applicable branch requires both string properties. This binding admits presence failure only; the shape does not verify the actual design-basis value.'
            elif req=='TRF-013' and cid.endswith('F01'):
                component='SPARQLConstraintComponent';review='Both fore/aft operands and all bounds are read; FILTER rejects an operating draught outside its corresponding inclusive bounds. Only fore is invalid in this fixture.'
            elif req=='TRF-017' and cid.endswith('F02'):
                component='SPARQLConstraintComponent' if w=='NO_SEMANTIC' else 'OrConstraintComponent'
                review='Explicit restriction=true chooses the restricted base; no additional propulsion power is represented in this fixture. The comparison rejects total 5000 != restricted 4200. Omission of additional power is a separate defect in F01 and is not admitted there.'
            elif req=='TRF-018' and not cid.endswith('F05'):
                component='SPARQLConstraintComponent';review='Class-dispatched numeric FILTER rejects MCR below represented required power or the 1000/2800 kW class floor. Wrong unit constants remain unrelated violations in the full shape.'
            elif req in ['IMO-006','IMO-008']:
                component='SPARQLConstraintComponent';review='A known ice classification triggers NOT EXISTS of a decimal metre quantity within the source inclusive interval. Each negative has one missing or out-of-range thickness, and each repaired graph supplies exactly that value.'
            elif req=='IMO26-009' and w=='NO_SEMANTIC':
                component='OrConstraintComponent';review='The branches explicitly require iceAccretionLikely true/false; when true every represented required antenna must have prevention=true. Other prerequisites and antenna type are independently checked.'
            if component:
                shape=Graph().parse(r['shape_path'])
                source=list(shape.subjects(audit.S.targetClass,audit.N.ship))[0]
                if req=='I2-019':source=next(shape.subjects(audit.S['class'],audit.N.structuralMember))
                binding=dict(paths=[],components=[component],focus=[str(focus)],reviewed_logic=review)
                if component=='SPARQLConstraintComponent':
                    candidates=[q for c in shape.objects(source,audit.S.sparql) for q in shape.objects(c,audit.S.select) if query_selector is None or query_selector in str(q)]
                    assert len(candidates)==1,(cid,w,len(candidates))
                    binding['query_sha256']=hashlib.sha256(str(candidates[0]).encode()).hexdigest()
                else:
                    binding['logic_fingerprint']=audit.logic_fingerprint(shape,source,component);assert binding['logic_fingerprint']
                spec['admissible_semantics'][w].append(binding)
                records.append(dict(case_id=cid,workflow=w,shape_path=r['shape_path'],shape_sha256=audit.sha(r['shape_path']),binding=binding))
        assert frozen_repair==(spec['removed_triples'],spec['added_triples'],spec['fixture_oracle'])
    audit.dump(P,specs)
    audit.dump(audit.HERE/'batch50_constraint_review.json',dict(records=records,source_independent_fixture_review=str(audit.HERE/'batch50_fixture_review.json'),repairs_changed=False,validation_reports_read=False))
    print('Reviewed frozen constraint bindings:',len(records))
if __name__=='__main__':bind()
