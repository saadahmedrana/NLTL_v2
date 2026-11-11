"""Small offline explanation probes; never replace full-shape verdicts."""
from pathlib import Path
import hashlib
from rdflib import Graph, RDF, Literal
from rdflib.collection import Collection
import audit
BASE=audit.HERE/'outputs/20261108T124921Z'
BATCH=BASE/'review_batches/batch50'

def run_probes():
    rows=audit.read(BASE/'retained_rows.json');idx={(r['condition'],r['case_id']):r for r in rows};records=[]
    for cid in ['I2-006-F01','I2-006-F02','I2-006-F03']:
        r=idx['NO_SEMANTIC',cid];shape=Graph().parse(r['shape_path']);probe=audit.clone(shape)
        data=Graph().parse(BATCH/'reviewed/corrected_fixtures/NO_SEMANTIC'/cid/'repaired_fixture.ttl')
        ship=next(data.subjects(RDF.type,audit.N.ship));intent=data.value(ship,audit.N.asternIceOperationIntent)
        source=next(probe.subjects(audit.S.targetClass,audit.N.ship));head=probe.value(source,audit.S['or'])
        branches=list(Collection(probe,head))
        selected=[b for b in branches if any((p,audit.S.hasValue,intent) in probe for p in probe.objects(b,audit.S.property))]
        assert len(selected)==1
        probe.remove((source,audit.S['or'],head));probe.add((source,audit.S.node,selected[0]))
        folder=BATCH/'cause_probes'/cid;folder.mkdir(parents=True,exist_ok=True)
        probe.serialize(folder/'applicable_branch_shape.ttl',format='turtle')
        result=audit.validate(data,probe,folder,'repaired_applicable_branch')
        rec=dict(case_id=cid,workflow='NO_SEMANTIC',diagnostic_only=True,selection='Existing asternIceOperationIntent=true, not a passing-branch search',source_shape_sha256=audit.sha(r['shape_path']),removed_triples=audit.triples(set(shape)-set(probe)),added_triples=audit.triples(set(probe)-set(shape)),result=result)
        audit.dump(folder/'record.json',rec);records.append(rec)
    for w,cid in [('NO_SEMANTIC','TRF-017-F02'),('SINGLESHOT','I2-004-G-F02')]:
        r=idx[w,cid];shape=Graph().parse(r['shape_path']);source=next(shape.subjects(audit.S.targetClass,audit.N.ship))
        data=Graph().parse(BATCH/'reviewed/corrected_fixtures'/w/cid/('negative_fixture.ttl' if cid=='TRF-017-F02' else 'repaired_fixture.ttl'))
        ship=next(data.subjects(RDF.type,audit.N.ship));queries=[q for c in shape.objects(source,audit.S.sparql) for q in shape.objects(c,audit.S.select)];assert len(queries)==1
        query=str(queries[0]);result=list(data.query(query.replace('$this','?this'),initBindings={'this':ship}))
        rec=dict(case_id=cid,workflow=w,diagnostic_only=True,query_sha256=hashlib.sha256(query.encode()).hexdigest(),returned_rows=[[str(v) for v in row] for row in result],query_unchanged=True,explanation='Generated FILTER references ?restriction from outside UNION groups; the recorded engine returns no violation despite 5000 != 4200.' if cid=='TRF-017-F02' else 'The generated SELECT selects the valid maximum-displacement state as a violation; the independently repaired 12 kt graph still rejects.')
        folder=BATCH/'cause_probes'/cid;folder.mkdir(parents=True,exist_ok=True);audit.dump(folder/'query_probe.json',rec);records.append(rec)
    audit.dump(BATCH/'cause_probes.json',records)
    print('Saved',len(records),'diagnostic explanation probes; no scores changed')
if __name__=='__main__':run_probes()
