# Figure data summary

Accuracy averages the fraction of correct cases for each requirement.
Unsuccessful outputs receive no accuracy credit.
Coverage counts requirements with a completed verdict for every assigned case, regardless of correctness.
Manual segment labels are counts; segment widths are percentages of the reviewed sample.
Models are single-pass outputs on a separate common sample, not final NLTL_v2 outputs.

| Group | Condition | Accuracy (%) | Coverage (%) | Requirements | Cases |
|---|---|---:|---:|---:|---:|
| Overall | Single-shot | 68.47 | 82.46 | 268 | 2160 |
| Overall | NLTL_v2 | 76.11 | 91.79 | 268 | 2160 |
| Direct static | Single-shot | 70.07 | 83.68 | 190 | 1516 |
| Direct static | NLTL_v2 | 76.38 | 92.63 | 190 | 1516 |
| Direct calculation | Single-shot | 62.64 | 75.61 | 41 | 337 |
| Direct calculation | NLTL_v2 | 79.83 | 92.68 | 41 | 337 |
| Complex readiness | Single-shot | 66.70 | 83.78 | 37 | 307 |
| Complex readiness | NLTL_v2 | 70.61 | 86.49 | 37 | 307 |

| Model | Stage | Accuracy (%) | Coverage (%) | Requirements | Cases |
|---|---|---:|---:|---:|---:|
| Luna | Single-pass | 72.42 | 84.00 | 50 | 373 |
| Sol | Single-pass | 88.76 | 100.00 | 50 | 373 |
| Gemini | Single-pass | 71.14 | 90.00 | 50 | 373 |
| GPT-OSS | Single-pass | 52.06 | 68.00 | 50 | 373 |
