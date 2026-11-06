# 1.4.3 publication receipt

Tachyon API 1.4.3 is published on [PyPI](https://pypi.org/project/tachyon-api/1.4.3/) and [GitHub Releases](https://github.com/jmpanozzoz/tachyon_api/releases/tag/v1.4.3).

Tag `v1.4.3` resolves to `7f00399b8898b83956cdbf2bf8f2b1013c2d4044`. The portable wheel and sdist are the exact locally validated pair. PyPI SHA256 values and independently downloaded GitHub release files match the manifest. [Machine receipt](publication.json) records hashes and verification time.

The [landing](https://tachyonapi-web.vercel.app/) now reads package/Python/license metadata from PyPI, repository/release metadata from GitHub, and version-bound evidence from the matching tag. Its evidence export rejects stale runtime hashes; unmeasured future versions show no invented comparison.

All 40 local publication gates passed: 933 source/example tests per Python 3.10–3.13, 229 contracts per original and sdist-rebuilt wheel. One early Uvicorn gate hit TCP reset during an unread rejected upload response; the network assertion was narrowed to rejection headers and reconnect safety, and all gates were regenerated. No runtime behavior or body-limit protection was relaxed. Execution is macOS ARM64, without a Linux/Windows or long-duration production claim.

The [published-package FastAPI benchmark](fastapi-benchmark.md) and [raw data](fastapi-benchmark.json.gz) were collected after publication in an isolated environment. They supplement the immutable release tag; no tag was moved or artifact rebuilt after upload.
