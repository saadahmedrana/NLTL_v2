# v0.6.0 source-grounded development pilot — stopped

The pilot stopped on its first HTTP request: I2-004 Single-shot generation received HTTP 403 from the Aalto gateway: “Caller IP address is not allowed. Access denied. - Ensure that you are connected from Aalto network.” No model output/candidate was returned. No NLTL, review, repair or later-requirement calls were sent. No automatic or manual retry was attempted. This is an infrastructure-blocked run, not an observed model-performance comparison.

## Preflight

Local HEAD and remote main matched `495f8c69e7213fac6d83cf28613cf9821b5794c3`; the working tree was clean. Installed/source v0.6.0 modules matched byte-for-byte. Snapshot hashes preserve implementation, prompts, base/resolved configurations and source/schema inputs. No few-shot examples were supplied. Both workflows’ initial source/schema/example context and settings were identical for every requirement, verified before dispatch.

The production snapshot contains no evaluation data, witnesses, solution profiles, bespoke permissions or historical shapes. The production resource capability and filesystem audit deny those paths and original project/history reads. Ignored preparation fields were projected out of snapshot JSON, with exact context/request equivalence asserted against the originals. No requirement-specific compliance witness or expected execution outcome was supplied.

## Outcomes and denominators

All 30 reviewed cases remain in each workflow’s primary denominator: 14 positive, 16 negative. All 16 reviewed counterparts remain listed. For **each workflow**: positive acceptance 0/14, strict intended detection 0/16, missed defects 0, unrelated rejection 0, unresolved attribution 0, positive NO_VERDICT 14 and negative NO_VERDICT 16 — total NO_VERDICT **30/30**. Those zero credits reflect absent outputs, not measured failures on executable shapes. Ordinary agreement has 0 executable agreements, 0 disagreements and 30 no-verdict cases. No exclusions were applied.

| Requirement | Positive | Negative | Counterparts | NO_VERDICT per workflow |
|---|---:|---:|---:|---:|
| I2-004 | 3 | 3 | 3 | 6 |
| I2-005 | 1 | 4 | 4 | 5 |
| IMO-001 | 2 | 3 | 3 | 5 |
| TRF-010 | 6 | 2 | 2 | 8 |
| TRF-035 | 2 | 4 | 4 | 6 |

There are no saved candidates to independently validate. Evaluation is therefore explicit no-verdict accounting, with no invented validation outcomes. Initial-versus-selected-final recovery/regression comparisons are unassessable. Budgets 2–6 all select no candidate and retain 30/30 no verdicts. No deterministic or reviewer findings were produced; unsupported feedback, false acceptance and repair usefulness cannot be assessed.

## Calls and timing

One HTTP generation dispatch, one gateway rejection, zero successful model responses, zero review/repair calls and zero auxiliary retries. The failed HTTP request took 0.376 seconds; recorded dispatch-loop elapsed time was 0.687 seconds. No token usage was returned; token counts and billing are unknown, not asserted zero. See `metrics.json`.

## Status classification caveat

The frozen Runner recorded REQUEST_INTEGRITY_FAILURE because the wrapper’s generic error label contained the word INTEGRITY. The actual preserved ledger establishes an HTTP 403 network-access denial; no candidate/hash mismatch was demonstrated. This distinction is recorded separately without altering the saved run or frozen code.

## Next step

Verify that this machine’s traffic reaches the Aalto gateway through an allowed network/VPN route. Do not reuse this stopped experiment destination. A new explicitly authorized fresh pilot can follow after network access is restored. This run does not justify expanding development coverage, selecting a budget or claiming workflow superiority. No earlier test-guided or seeded diagnostic results are pooled; the 50-requirement study was not started.
