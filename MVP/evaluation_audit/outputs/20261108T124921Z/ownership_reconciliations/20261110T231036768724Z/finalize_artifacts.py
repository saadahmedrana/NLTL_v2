import sys,json,csv,copy
from pathlib import Path
p=Path(__file__).resolve().parent;sys.path.insert(0,str(p));import reconcile_ownership as m
before=m.read(p/'records_before.json');after=m.read(p/'records_after.json');plan=m.read(p/'plan.json');executions=m.read(p/'executions.json')
test=p/'test_reconciliation.py';test.write_text(test.read_text().replace("x['included_cases']","x['cases']"))
# An explicit withdrawal register makes superseded claims discoverable without
# modifying the archived historical evidence.
withdraw=[]
entries={e['case_id']:e for e in plan['entries']}
for cid in sorted(set(plan['underspecified_cases'])|set(plan['known_population_counterfactuals'])|{c for c,e in entries.items() if e.get('old_repair_invalid')}):
 old=before[cid];new=after[cid];oldpath=old.get('repaired_fixture')
 withdraw.append(dict(case_id=cid,requirement_id=old['requirement_id'],historical_repair=oldpath,historical_repair_sha256=m.sha(oldpath) if oldpath else None,historical_validity_claim=old.get('independent_repaired_valid','INHERITED_PRIOR50_SPEC'),current_historical_repair_status='INVALID_CLEAR_CONTRACT_OWNER' if cid in entries else 'WITHDRAWN_NOT_INTENDED_ONLY' if cid in plan['known_population_counterfactuals'] else 'UNESTABLISHED_UNDERSPECIFIED_CONTRACT',current_candidate_validity=new.get('independent_repaired_valid'),current_candidate=entries.get(cid,{}).get('repaired_fixture'),record=str(p/'records_after.json')+'#/'+cid,reason=new.get('repair_history') or new.get('blockers')))
m.save('repair_validity_withdrawals.json',withdraw);m.csvout('repair_validity_withdrawals.csv',withdraw)
flags=[]
for f in m.read(m.OWN/'findings.json'):
 if f['primary_finding']!='FIXTURE_VIOLATES_CLEAR_SCHEMA':continue
 e=entries[f['case_id']];flags.append(dict(ownership_flag=f,interpretation=dict(intentional_negative_mutation=e['case_id']=='TRF-050-F05',unintended_original_fixture_defect=e.get('unintended_original_fixture_defect',False),invalid_supplied_repaired_counterfactual=e.get('old_repair_invalid',False)),revised_status=after[e['case_id']]['workflows'][f['workflow']]['status'],evidence=str(p/'TRF-050-F05_causal_review.json') if e['case_id']=='TRF-050-F05' else str(p/'pair_reviews'/f'{e["case_id"]}.json')))
m.save('confirmed_flag_reconciliation.json',flags)
usage=[]
for j in executions:
 entry=entries.get(j['case_id']);diagnostic=j['kind']=='repaired' and entry and bool(entry.get('blockers'))
 usage.append(dict(key=j['key'],workflow=m.audit.WORKFLOWS[j['condition']],case_id=j['case_id'],purpose='DIAGNOSTIC_UNVERIFIED_COUNTERFACTUAL' if diagnostic else 'ORDINARY_VERDICT_ONLY' if j['kind']=='ordinary' and (not entry or entry.get('blockers')) else 'REVIEWED_PAIR_AND_ORDINARY_NEGATIVE' if j['kind']=='ordinary' else 'REVIEWED_COUNTERFACTUAL',strict_credit_allowed=not diagnostic and bool(entry) and not bool(entry.get('blockers')),conforms=j['result']['conforms'],report=j['result']['report_path'],data_sha256=m.sha(j['data']),shape_sha256=j['shape_sha256']))
m.csvout('validation_usage.csv',usage)
# Full retained input manifest, shared across workflows, unmodified labels.
manifest=[]
for r in m.ROWS:
 if r['condition']!='NO_SEMANTIC':continue
 file=p/'benchmark'/r['rdf_path'];manifest.append(dict(case_id=r['case_id'],requirement_id=r['requirement_id'],expected=r['expected'],fixture=str(file),sha256=m.sha(file),workflows=list(m.audit.WORKFLOWS),excluded=r['case_id']=='TRF-002-F02'))
assert len(manifest)==2160;m.save('benchmark_manifest.json',manifest)
causes=[]
for cid,r in after.items():
 for w,v in r.get('workflows',{}).items():
  cause=v.get('likely_cause') or v.get('failure_cause') or {'primary':'NOT_RECLASSIFIED_IN_THIS_RECONCILIATION'}
  causes.append(dict(case_id=cid,requirement_id=r['requirement_id'],workflow=m.audit.WORKFLOWS[w],state=r['state'],status=v['status'],likely_cause=cause,ownership_schema_status='UNRESOLVED_UNDERSPECIFIED' if cid in plan['underspecified_cases'] else 'CONFIRMED_FIXTURE_SIDE_RECONCILED' if cid in entries else 'NOT_REVIEWED_IN_THIS_RECONCILIATION',blockers=r.get('blockers',[])))
m.csvout('current_status_cause_ledger.csv',causes)
summary=m.read(p/'SUMMARY.md').split('\n## Denominator changes and a fixed before/after comparison')[0]
summary+='''
## Denominator changes and a fixed before/after comparison

The current common fully classified subset covers **553 cases / 158 requirements**; **651 cases remain blocked** and the **one existing exclusion** is unchanged. Its reduction from 611 is 52 underspecified-owner cases plus eight TRF-130 cases withdrawn, offset by two newly completed TRF-036 cases. No valid test is excluded for a generated-shape failure.

On the identical **551-case intersection** of the old and new fully classified subsets:

| Workflow | Strict before → after | Unrelated/additional before → after | Missed | No verdict |
|---|---:|---:|---:|---:|
| NLTL_v2 | 332 → 351 | 157 → 138 | 54 | 8 |
| Single-shot | 320 → 318 | 121 → 123 | 38 | 72 |

20 canonical counterfactuals now meet the independently reviewed source/contract and intended-only gates. Eight TRF-130 candidates do not. Ordinary results include 65 changed-input executions; 43 repaired executions were saved, including six TRF-130 reports subsequently downgraded to diagnostic evidence when the oracle gap was found. All 108 executions are individually recorded; none of those diagnostic reports supplies strict credit. No shape transformation was performed.

`repair_validity_withdrawals.json` explicitly supersedes old repair claims without changing their archived files. `confirmed_flag_reconciliation.json` preserves every one of the 42 workflow/case fixture-side flags and its interpretation. `validation_usage.csv` distinguishes ordinary, reviewed-pair and subsequently unverified counterfactual evidence. `benchmark_manifest.json` identifies every retained shared fixture. `current_status_cause_ledger.csv` is a status view; entries outside this reconciliation retain their prior cause analysis rather than receiving a newly guessed cause.
'''
(p/'SUMMARY.md').write_text(summary)
(p/'README.md').write_text('''# Versioned ownership / strict-audit reconciliation

Read `SUMMARY.md`, `records_after.json` and `repair_validity_withdrawals.json` together. The authoritative baseline remains 20261108T124921Z. After publication, `evaluation_audit/authoritative_run.json` points to this immutable current record snapshot and fixture version. Archived all_negatives/records and old 50-case specifications are historical evidence and retain their original claims; those claims are explicitly superseded where listed here.

No setup changes: workspace `.venv`, Python 3.13.5, rdflib 7.6.0, pyshacl 0.31.0, recorded baseline options. No model calls or shape modifications.

From the MVP workspace, run the read-only checks:

```sh
.venv/bin/python evaluation_audit/outputs/20261108T124921Z/ownership_reconciliations/20261110T231036768724Z/test_reconciliation.py
```

`reconcile_ownership.py` phases prepare/validate/review/apply document the reproducible implementation. Validation is fingerprint-checkpointed. The completed phase must not be repeated merely to rebuild reports. Use saved artifacts for review. `apply` publishes pointers only after checking all protected original artifacts; it never overwrites the archived records or benchmark.

The historical semantic regression `test_owner_mismatch_is_unrelated_even_if_repaired_passes` encodes the withdrawn TRF-050 rule and is superseded by `test_trf050_domain_consequence_is_scoped_and_never_rerun` here. The original test file is preserved. Applicable existing synthetic scoring and static branch tests were run separately; no completed historical pair was replayed.

The independent oracle has separate actual-graph explicit-owner/type/unit checks and a retained source-logic oracle using an exact inverse-placement view. The latter alone cannot certify ownership or omitted declared inputs. TRF-130 remains unresolved on that basis. Underspecified contracts are unchanged.
''')
print('withdrawals',len(withdraw),'flags',len(flags),'diagnostic repaired',sum(x['purpose']=='DIAGNOSTIC_UNVERIFIED_COUNTERFACTUAL' for x in usage))
