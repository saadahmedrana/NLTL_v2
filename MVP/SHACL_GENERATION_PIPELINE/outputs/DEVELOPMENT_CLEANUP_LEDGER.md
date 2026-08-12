# Development output cleanup ledger

Cleanup date: 2026-08-12

The following generated directories were removed after their useful findings
were incorporated into the R2 repair record, final accepted runs, evaluator
tests, and the Batch 01 engineering assessment.

## Removed generation runs

| Run | Status | Reason |
|---|---|---|
| `RUN-IMO-057-20260812T101117651467Z` | R1 max attempts | Superseded by the R2 vocabulary repair and accepted R2 run. |
| `RUN-IMO-057-20260812T103940644322Z` | Interrupted | Sandbox-network diagnostic; no completed semantic generation. |
| `RUN-IMO-088-20260812T101427092354Z` | R1 max attempts | Superseded by controlled-value retrieval fix and accepted R2 run. |
| `RUN-IMO-088-20260812T102506817888Z` | R1 accepted | Superseded by the R2-bound accepted run used in final RDF evaluation. |
| `RUN-IMO26-014-20260812T093802863061Z` | R1 accepted | Earlier duplicate; the later accepted R1 run is retained. |

## Removed evaluation reruns

Four earlier executions of `GENERATED-SHAPES-R2-IMO-057-IMO-088` were removed.
They were superseded while correcting workbook boolean counts, shortening Excel
report text, adding file hashes, loading the locked ontology, and binding the
manifest hash. The final retained evaluation is:

`EVAL-GENERATED-SHAPES-R2-IMO-057-IMO-088-20260812T110525688558Z`

## Retained

- Latest accepted runs for IMO-025, IMO-033, IMO-057, IMO-075, IMO-088, and
  IMO26-014.
- Final hash-bound RDF evaluation and tracker.
- R1/R2 vocabulary locks and concise revision evidence.
- Current source inputs, Batch 01 development artifacts, and regression tests.

## Batch 01 restart cleanup

After the first R3 live attempt identified the genuine TRF-001 provision-scope
vocabulary gap, two non-evidence runs were removed before the clean restart:

| Run | Status | Reason |
|---|---|---|
| `RUN-TRF-001-20260812T124949951616Z` | Network-only interruption | Sandbox-network diagnostic with no API response. |
| `RUN-TRF-002-20260812T125205231737Z` | Interrupted | Stopped immediately after the R3 hash changed; its incomplete result cannot be compared under the repaired development binding. |

The completed `RUN-TRF-001-20260812T125010414068Z` vocabulary-gap run is
retained as evidence for adding provision-scoped applicability terms.
