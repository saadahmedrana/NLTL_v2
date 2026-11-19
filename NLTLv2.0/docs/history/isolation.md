# Independent installation and isolation proof

The project was copied to a separate temporary project directory. A fresh Python 3.13.5 environment installed its declared dependencies and built the package from that copy. Installation used local wheels with `--no-index` while an OS sandbox denied network access and every read beneath the verified original repository and external credentials directory. No old virtual environment, runtime import, symlink or data dependency was used.

Before configuration checks and smoke tests, `smoke_tests/isolated_entry.py` deliberately attempted to read the old runner's pyproject.toml and required PermissionError. It also checked that the installed package and sys.path did not point to the denied repository. `smoke_tests/isolation_check.py` checked the project for symlinks, absolute workspace references and old runtime imports. The original-repository path is an explicit command argument, not a project resource dependency.

The completed external regression is retained separately from the latest 43-test control suite. Later changes added source/ontology context and three targeted checks without altering the certified fixtures, independent oracle or source-authored reference controls, so the unchanged 37-case regression was not repeated. Its results are not generated-shape scores.

To repeat on macOS, from a temporary copy with its own external virtual environment:

```sh
# First install dependencies normally, or stage wheels before disabling networking.
python3 -m venv ../isolated-env
../isolated-env/bin/python -m pip install -r requirements-lock.txt .
# Construct a sandbox profile using your verified original repository path.
# This path is denied, not used to resolve project inputs.
python3 - '/path/to/original/NLTL_v2' /tmp/nltl-isolation.sb <<'PY'
import json,sys,pathlib
old=pathlib.Path(sys.argv[1]).resolve()
pathlib.Path(sys.argv[2]).write_text('(version 1)\n(allow default)\n(deny network*)\n(deny file-read* (subpath '+json.dumps(str(old))+'))\n(deny file-read* (subpath '+json.dumps(str(old.parent/'env'))+'))\n')
PY
sandbox-exec -f /tmp/nltl-isolation.sb ../isolated-env/bin/python -I \
  smoke_tests/isolated_entry.py "$PWD" '/path/to/original/NLTL_v2' check
sandbox-exec -f /tmp/nltl-isolation.sb ../isolated-env/bin/python -I \
  smoke_tests/isolated_entry.py "$PWD" '/path/to/original/NLTL_v2' smoke
# isolated_entry repeats the control suite; repeat all 37 reference cases explicitly:
sandbox-exec -f /tmp/nltl-isolation.sb ../isolated-env/bin/python -I \
  -m nltlv2 --project "$PWD" evaluate-core
```

The existing desktop sandbox required an elevated invocation to create the additional OS sandbox. Those invocations succeeded. Package acquisition was the only network activity; no model service was contacted. The copy contains neither credentials nor a virtual environment. The ordinary README commands are cross-platform; OS-level denial above is macOS-specific.
