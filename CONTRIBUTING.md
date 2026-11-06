# Contributing

Start from `dev` and keep each change on a feature/fix branch. Describe the user
behavior, migration impact and validation. Keep runtime dependencies separate
from example, benchmark and development tools. Follow [the repository guide](CLAUDE.md).

Supported Python versions are 3.10–3.13. Install the checkout and the harness:

```sh
python -m pip install -e '.[test]' -r scripts/test-requirements.txt
python -m ruff check tachyon_api tests benchmark scripts example
python scripts/quality_cycle.py --engine python --output /tmp/tachyon-quality.json
```

The persistent reference tests require explicit disposable PostgreSQL/Redis
services. Set `TEST_DATABASE_URL` to a database whose name ends in `_test` and
`TEST_REDIS_URL` to an isolated Redis instance/database. They truncate their test
tables and clear only `reference:*` Redis keys. Run these tests serially. Without
the database variable they report skips; those skips are not integration evidence.

```sh
python -m pytest tests/ example/tests/
```

Keep tests focused on observable contracts: resource ownership, authorization,
errors, transport behavior and generated projects that execute outside this
checkout. Record actual platform/interpreter coverage. New public behavior needs
documentation and migration notes. Do not alter historical release evidence or
reuse its measurements for changed runtime bytes.

For release preparation, use [local release checks](docs/quality/local-release.md).
For Linux, use the [validation runbook](docs/quality/linux-validation.md). This
repository's GitHub Actions billing block is independent of test correctness;
configured workflows do not establish execution evidence.
