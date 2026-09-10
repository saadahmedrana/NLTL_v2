from pathlib import Path
import hashlib
import json
import sys


def find_repo():
    candidates=[Path.cwd(),Path(__file__).resolve().parent]+list(Path(__file__).resolve().parents)
    seen=set()
    for c in candidates:
        c=c.resolve()
        if c in seen:
            continue
        seen.add(c)
        if (c/'MVP'/'BENCHMARK_VOCABULARY'/'FINAL_LOCK_R13'/'requirement_term_index.json').exists():
            return c
    raise RuntimeError('Could not locate NLTL_v2 repository root')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    repo=find_repo()
    root=repo/'MVP'/'SHACL_GENERATION_PIPELINE'/'evaluation'/'BEHAVIORAL_RDF_R13'
    letters='abcdefghi'
    all_reqs=[]
    all_case_ids=[]
    all_paths=[]
    total_cases=0
    errors=[]

    print('I2 systematic benchmark integrity A-I')
    for letter in letters:
        lock_path=root/'locks'/f'i2_batch_{letter}_fixture_lock.json'
        manifest_path=root/'manifests'/f'i2_batch_{letter}_manifest.jsonl'
        if not lock_path.exists():
            errors.append(f'Missing lock: {lock_path.name}')
            continue
        if not manifest_path.exists():
            errors.append(f'Missing manifest: {manifest_path.name}')
            continue
        lock=json.loads(lock_path.read_text())
        rows=[json.loads(x) for x in manifest_path.read_text().splitlines() if x.strip()]
        reqs=lock.get('requirements',[])
        n=lock.get('case_count')
        if n!=len(rows):
            errors.append(f'Batch {letter.upper()} case_count={n} but manifest has {len(rows)} rows')
        row_reqs=sorted(set(r['requirement_id'] for r in rows))
        if sorted(reqs)!=row_reqs:
            errors.append(f'Batch {letter.upper()} lock/manifest requirement set differs')
        hash_bad=[]
        for rel,h in lock.get('frozen_files',{}).items():
            p=root/rel
            if not p.exists() or sha256(p)!=h:
                hash_bad.append(rel)
        if hash_bad:
            errors.append(f'Batch {letter.upper()} frozen hash mismatches: {len(hash_bad)}')
        for r in rows:
            if 'generated_shacl_inspected' in r and r.get('generated_shacl_inspected') is not False:
                errors.append(f"Batch {letter.upper()} case {r.get('case_id')} explicitly records generated_shacl_inspected other than false")
            all_case_ids.append(r['case_id'])
            all_paths.append(r['rdf_path'])
        all_reqs.extend(reqs)
        total_cases+=len(rows)
        print(f'Batch {letter.upper()}: {len(reqs):2d} requirements / {len(rows):3d} cases / hashes '+('PASS' if not hash_bad else 'FAIL'))

    # Verify the older Pilot-02 lock remains byte-for-byte respected after the E/F repair
    # and after later collision-safe batches G/H.
    pilot_lock_path=root/'locks'/'pilot_02_fixture_lock.json'
    if not pilot_lock_path.exists():
        errors.append('Missing Pilot-02 lock')
        pilot_bad=[]
    else:
        pilot=json.loads(pilot_lock_path.read_text())
        pilot_bad=[]
        for rel,h in pilot.get('hashes',{}).items():
            p=root/rel
            if not p.exists() or sha256(p)!=h:
                pilot_bad.append(rel)
        if pilot_bad:
            errors.append(f'Pilot-02 frozen hash mismatches: {len(pilot_bad)}')
    print('Pilot 02 frozen hashes: '+('PASS' if not pilot_bad else 'FAIL'))

    if len(all_reqs)!=len(set(all_reqs)):
        dup=sorted({x for x in all_reqs if all_reqs.count(x)>1})
        errors.append('Systematic requirements duplicated across A-I: '+', '.join(dup))
    if len(all_case_ids)!=len(set(all_case_ids)):
        errors.append('Duplicate systematic case IDs exist across A-I')
    if len(all_paths)!=len(set(all_paths)):
        errors.append('Duplicate systematic RDF paths exist across A-I')

    unique_reqs=len(set(all_reqs))
    print(f'Unique systematic I2 requirements: {unique_reqs}')
    print(f'Systematic RDF cases: {total_cases}')
    if unique_reqs!=45:
        errors.append(f'Expected 45 systematic I2 requirements, found {unique_reqs}')
    if total_cases!=499:
        errors.append(f'Expected 499 systematic I2 cases, found {total_cases}')

    print('Overall integrity status: '+('PASS' if not errors else 'FAIL'))
    if errors:
        print('\nDiagnostics:')
        for e in errors:
            print('-',e)
        raise SystemExit(1)


if __name__=='__main__':
    main()
