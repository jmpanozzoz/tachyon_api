# 16. Portable builds and upgrading from Cython

Starting with **1.4.1**, Tachyon now has one Python
implementation and produces one `py3-none-any` wheel plus an sdist. Python
3.10–3.13 remains supported. Building Tachyon itself needs neither Cython nor a
C/Rust compiler; dependencies such as msgspec, orjson and httptools may still need
native wheels or their own build tools. The older filename preserves documentation links.

## Build and verify

```sh
python -m build
python scripts/quality_cycle.py --output quality-python.json
python scripts/test_installed_wheel.py --engine python
```

Run the installed-package check after installing the candidate wheel. It copies
contracts into a separate directory, clears PYTHONPATH, verifies every expected
Python module outside the checkout and rejects leftover native files. The release
process also rebuilds the sdist and tests that installed package on each supplied
interpreter. See [local release](quality/local-release.md).

`[fast]` remains a deprecated empty compatibility extra. It no longer installs
Cython or enables a different engine. `TACHYON_SKIP_CYTHON` is no longer needed and
has no effect. Requests keep the Python behavior tested in the previous release.

## Upgrade from 1.4.0

Use the normal package manager upgrade to 1.4.1, and restart worker processes. For editable installations or manually compiled checkouts, prefer a
fresh environment or clean checkout: old `.so`/`.pyd` files can shadow `.py` files.
Do not delete third-party native dependencies. The verification command above
rejects stale native modules inside Tachyon itself.

The [1.4.0 record](audits/1.4.0/LOCAL_RELEASE.md) describes that historical native
release. It is not the packaging policy for 1.4.1. Current validation must record
actual interpreter/platform coverage; a portable wheel does not establish that
Linux or Windows was tested.
