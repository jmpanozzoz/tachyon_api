# Local release without hosted Actions

Prepare a release with one portable Python wheel and one sdist. Run on every
available supported interpreter (3.10–3.13), retain source fingerprints and record
the actual OS/architecture. Portable packaging does not prove runtime compatibility
on systems that were not exercised. Third-party dependencies retain native requirements.

```sh
python scripts/local_release.py \
  --python /absolute/path/to/python3.10 \
  --python /absolute/path/to/python3.11 \
  --python /absolute/path/to/python3.12 \
  --python /absolute/path/to/python3.13 \
  --uv /absolute/path/to/uv \
  --output /absolute/path/to/new-release-directory \
  --duration 60 --concurrency 8
```

The output must be new and outside the checkout. The command freezes a snapshot,
creates an environment for each interpreter, checks Ruff and every Python module
origin, runs source/example tests, builds the wheel/sdist, rebuilds from the sdist
and tests both installed wheels outside the checkout. Rebuilt wheels stay outside
the upload directory; the same candidate portable wheel is tested on each interpreter.
A validated mixed-scenario HTTP soak runs on the first supplied interpreter only.
Add `--with-granian` to install Granian/websockets in the test environments and
exercise optional real-server contracts as part of each full source suite.
Its sampled RSS is distinct from traced Python allocations; a short run does not
establish production capacity or multi-hour stability.

Only one Python engine exists. No Cython/compiler toolchain is installed by this
process. Tests reject stale native modules and empty/mismatched inventories rather
than relying on `.pyx` discovery. Supported OS/interpreter jobs in workflow files
are configured coverage, not evidence that hosted runs happened.

```sh
python scripts/check_release_artifacts.py /absolute/path/to/artifacts --version 1.4.1
python -m twine check --strict /absolute/path/to/artifacts/*
```

The archive checker requires exactly one portable wheel and one sdist, validates
metadata, the safe orjson minimum, Python inventory, tags, RECORD hashes and CLI
entry point, and rejects retired Cython/native files. It does not execute requests.
Review scripts' `--help` for their current interfaces.

A successful preparation writes `manifest.json` with `complete: true`, check exit
codes, interpreter rows, logs and artifact hashes. This is **not publication**.

```sh
python scripts/publish_local.py --manifest /absolute/path/to/release/manifest.json --uv /absolute/path/to/uv --dry-run
```

Publication uses that exact completed manifest. The uploader rejects failed gates,
changed artifacts and paths outside its dist directory. Tokens come from existing
environment variables or `~/.pypirc`, never command arguments. Actual publication
requires the authorized release workflow after the reviewed source is merged;
remove `--dry-run` only for that release. Published hashes are checked against PyPI.
Do not overwrite or rebuild artifacts after a partial upload; inspect index state.

The [1.4.0 release](../audits/1.4.0/LOCAL_RELEASE.md) remains immutable historical
evidence, including its native wheels. It is not the current build policy.
