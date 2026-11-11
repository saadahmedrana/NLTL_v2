# Repair request dry run

Offline scripted responses; no environment secrets or API calls. The selected config, budgets, prompt sources and all source hashes are in manifest.json. Only output paths and Excel export differ from the selected config.

Each scenario/request_ledger.json binds candidate SHA/version, saved feedback and route. Complete developer/user text is saved for every request under runner_output/complete_requests/ and by the real runner under artifacts/. Failed negative-control requests are retained too. Fresh escape-hatch generation is distinct and does not promise inclusion of previous code.

This audits renderer/runner requests at the offline client boundary, not live provider delivery or automated repair quality. It does not install a live transport guard or change generation logic.
