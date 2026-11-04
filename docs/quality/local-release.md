# Local release from this host

A release can be prepared and uploaded from a local machine without GitHub
Actions. Local evidence applies to the operating system, architecture and Python
interpreters actually exercised. This Mac is arm64: its native wheels cover
macOS arm64 only. A portable wheel contains Tachyon's Python implementation;
its dependencies may still need their own compatible wheels or compilers.

## Artifact policy

Prepare one versioned directory containing exactly one source distribution,
exactly one `py3-none-any` wheel, and any independently built and tested native
wheels for that same version. Preserve logs and validation reports separately
from the files selected for upload. Never relabel a macOS native wheel as Linux,
Windows, x86_64, or a different CPython ABI.

The portable wheel is the fallback for supported interpreters and platforms
without a matching Tachyon native wheel. Its filename expresses the absence of
Tachyon-specific ABI/platform requirements, while `Requires-Python` restricts
installation to Python 3.10–3.13. See the official
[wheel compatibility tag specification](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/).
This fallback does not establish that every operating system was tested.

Build native macOS arm64 wheels with `MACOSX_DEPLOYMENT_TARGET=11.0` in a clean
build directory. Inspect the resulting tag: the intended floor is
`macosx_11_0_arm64`. The build host's newer macOS version must not accidentally
become the deployment floor. Each CPython 3.10–3.13 ABI needs its own native build
and test interpreter. Building on one interpreter does not create wheels for
all four. Do not claim compatibility below the tag's declared floor without
checking binary dependencies and running on that system.

Docker, if installed and running, may enable Linux container builds; its
availability alone proves neither manylinux compatibility nor successful tests.
Linux wheels require appropriate manylinux build/repair tooling and verification
for each architecture. Windows wheels require a suitable Windows build/test
host. These are separate work items when unavailable locally.

## Preparation and verification

1. Select the release version and reconcile package metadata, changelog and
   release notes. Confirm that the intended index can accept the chosen version;
   do not rely on overwriting an existing distribution filename.
2. Capture the exact reviewed source snapshot. Build outside the working tree
   so stale native extensions and generated build files cannot contaminate the
   portable wheel or sdist. Use `TACHYON_SKIP_CYTHON=1` for portable builds; a
   compilation failure must remain visible for native builds.
3. Build the sdist, then rebuild the portable and available native wheels from
   that sdist. Keep its Python, Cython and `.pxd` sources intact.
4. Run the full source and example suites in genuinely separate Python/native
   import environments for each available interpreter. Record unsupported or
   untested matrix entries explicitly.
5. Install each candidate wheel into a fresh environment and run the installed
   wheel contracts from outside the checkout. The repository helper
   `scripts/test_installed_wheel.py --engine python` (portable) or
   `--engine native` verifies installed module origins and runs the retained
   contract tests. Its interpreter must belong to the fresh install environment.
6. Check distribution metadata and archive consistency. Keep the exact artifact
   names, hashes, interpreter versions, platform and test results with the
   release evidence. These checks do not substitute for runtime tests.

The local preparation command uses one explicit interpreter per native ABI and
uv for isolated environments. Supply every interpreter actually available:

```sh
python scripts/local_release.py \
  --python /absolute/path/to/python3.10 \
  --python /absolute/path/to/python3.11 \
  --python /absolute/path/to/python3.12 \
  --python /absolute/path/to/python3.13 \
  --uv /absolute/path/to/uv \
  --output /absolute/path/to/release-output \
  --duration 60 --concurrency 8
```

`--python` is repeatable; `--uv` and `--output` are required. The example assumes
all four interpreters exist; omit unavailable ones and record the coverage gap.
The command prepares isolated snapshots, tests and artifacts; it does not
publish. `--duration` defaults to 60 seconds and `--concurrency` to 8. These load
settings define a bounded local check, not a production capacity claim.

Review `python scripts/local_release.py --help` for the installed script's exact
interface before running it.

The archive checker has no installation, upload or credential access:

```sh
python scripts/check_release_artifacts.py \
  --version 1.4.0 \
  --require-native \
  --native-platform macosx_11_0_arm64 \
  /absolute/path/to/release-artifacts

python -m twine check /absolute/path/to/release-artifacts/*
```

Use the chosen release version, rather than assuming the example version is
available. Omit `--require-native` and `--native-platform` for an explicitly
portable-only release. `--native-platform` asserts an exact platform tag for
every native wheel in that directory; omit it for a deliberately mixed-platform
release assembled from separately verified builds.

The checker verifies distribution name/version and Python requirements,
filename/WHEEL tag agreement, the purelib marker, Python fallback modules, every
expected native extension, RECORD hashes/sizes, the CLI entry point, and complete
sdist build/Python/Cython/declaration sources. It rejects native binaries in
portable wheels or sdists. It does not inspect native linker compatibility,
verify runtime behavior, prove reproducible compilation, or check index state.
Twine's check validates distribution rendering/metadata; it does not install the
package or run tests. See [Twine documentation](https://twine.readthedocs.io/en/stable/).

## Publication record

Publication is a separate action using the exact verified artifact set. The
publisher consumes the preparation manifest:

```sh
python scripts/publish_local.py \
  --manifest /absolute/path/to/release-output/manifest.json \
  --uv /absolute/path/to/uv \
  --dry-run
```

A dry run checks publication readiness without uploading. Actual upload uses the
same command without `--dry-run` and requires the user's release authorization
and a usable package-index credential. The publisher does not make an
unverified artifact set ready for release. Keep
credentials outside source files, arguments, logs and reports. A local release
does not require creating an Actions run. Preserve the package-index result and
artifact hashes, then reconcile the release notes and tag with what was actually
published. State which portable/native wheels exist and which platforms were
validated. Do not describe an unexecuted cross-platform matrix as passing.
