# Bounded TRF-010 development tests — completed

Frozen v0.2.0, model gpt-5.6-luna-2026-07-09, unchanged schema `ba247e3973b6afc36a9160ca170a31f863ceb3b0df497e07b7b3101dc7f347e4`. Git revision, working-tree changes, prompts, implementation, configs and source contracts were snapshotted before dispatch. All 1436 pre-existing output artifacts were rehashed unchanged; active source/config snapshot hashes still match. Credentials remained external and secret values were not copied.

**A: TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC.** No initial generation. One actual repair call plus one production review corrected the historical missing enumeration and accepted candidate v2. The only code change is the six-value sh:in list; all other constraint structure remains unchanged. Positives: 6/6; strict negatives: 2/2; unrelated rejection/no verdict: 0/0. The re-evaluated seed is separately labelled diagnostic (1/2 strict negatives); it is not a new historical score.

**B: Fresh paired pilot.** One generation per method, identical initial requests/context. Both generated the correct enumeration immediately. NLTL accepted candidate 1 after one review, with no repair. Each method: 6/6 positive acceptance, 2/2 strict intended detection, 8/8 ordinary agreement, zero unrelated rejection and zero no verdicts. Two repaired counterparts pass for every corrected/fresh candidate. No evaluation results entered acceptance, prompts or repair.

Actual usage: five provider calls total (two fresh generations, one targeted repair, two reviews), 62,765 tokens. Targeted diagnostic: 26,143 tokens / 6.910s; fresh Single-shot: 12,097 / 2.767s; fresh NLTL: 24,525 / 6.254s. Exact input/output/cache/reasoning counts, provider time, live driver time and offline evaluation time: usage_summary.json. All five responses reported the requested model and completed status. No transport/format retries, integrity failure, contradictory feedback or fresh regeneration occurred.

Maximum cardinality remains unresolved. Arm A retained its seed's maxCount 1; neither fresh shape adds it. Category assignment was evaluated, not engineering qualification or exhaustive multiplicity/robustness. No six-requirement batch or 50-requirement study ran.

**Recommendation:** preflight source/schema bindings for the remaining five reviewed requirements, then seek separate authorization for a six-requirement development pilot under the same independent-evaluation and stop rules. This demonstrates one live targeted repair and successful fresh operation on TRF-010, not general repair quality or an advantage over Single-shot.

Separate arm evidence:
- Arm A: outputs/experiments/20261113T120208710658Z_TRF010_TARGETED_REPAIR_DEVELOPMENT_DIAGNOSTIC/REPORT.md
- Arm B: outputs/experiments/20261113T120523850518Z_TRF010_FRESH_PAIRED_DEVELOPMENT_PILOT/REPORT.md
