# Offline repair-request audit

The user selected FULL_REPAIR_V2 RUN_01. See latest_completed.json for the authoritative completed audit and its report. Historical evaluation authority remains separate and unchanged.

From MVP:

```sh
.venv/bin/python SHACL_GENERATION_PIPELINE/scripts/audit_repair_requests.py --config SHACL_GENERATION_PIPELINE/experiments/FULL_REPAIR_V2/CONFIGS/pipeline.full-repair-v2-run01.json
PYTHONPATH=SHACL_GENERATION_PIPELINE/src .venv/bin/python -m unittest SHACL_GENERATION_PIPELINE.tests.test_repair_request_audit SHACL_GENERATION_PIPELINE.tests.test_full_repair_v2 SHACL_GENERATION_PIPELINE.tests.test_pipeline_offline
```

No API client or environment secrets are used. HTTP/socket access and dotenv loading are blocked during the scripted scenarios. Output and Excel settings are the only effective-config overrides. The tool saves full requests and fails nonzero for missing, stale or truncated normal-repair code or feedback version mismatches. Five deliberately failing controls verify the guard; these expected failures do not make a successful audit fail.

This tool audits existing request plumbing. It does not install a production transport guard, add the proposed canonical-unit detector, regenerate regulatory shapes, or modify the selected experiment config. The selected live output already contains historical runs; a new measured experiment needs an explicit fresh output/run identity.
