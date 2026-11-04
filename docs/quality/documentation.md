# Documentation maintenance

Documentation changes belong with the code that changes the public contract.
Before closing a change, check the matching guide, README, migration notes,
CLI-generated examples and changelog. Describe observable behavior and explicit
unsupported cases; do not add features to preserve an inaccurate example.

Use the EGM drift-report skill to read each affected document and its referenced
source sequentially. Record concrete differences per document, fix confirmed
drift, then compare again. A drift audit does not establish convergence of the
separate Goldfish review-loop protocol.

`tests/test_documentation_contracts.py` compiles Python fences, exercises selected
applications and CLI tutorials, verifies documented errors/authentication, and
checks local links in maintained guides. Run it with the example suite:

```sh
python -m pytest tests/test_documentation_contracts.py example/tests -q
```

These checks do not execute every prose statement, shell command or third-party
service. Source comparison is still required. Consult Context7/current primary
documentation when a claim depends on a third-party API.

Keep changing test counts, platform coverage and performance measurements in dated
evidence reports, linked from guides. Distinguish configured CI jobs, actual local
results, source checkout tests and installed-package tests. Publication requires
a receipt or index verification, not just successful build logs.

Historical audit reports and old changelog entries describe their original
snapshot. Retain their evidence and add a prominent current-status link instead
of silently rewriting old results. After publishing, update active release status,
platform availability and migration notes; post-publication documentation/example
changes are recorded under Unreleased until their next release.

The [2026-11-04 drift report](../audits/1.4.0/documentation/2026-11-04_DRIFT_REPORT.md) records the 1.4.0 reconciliation and observed repairs. Its [validation](../audits/1.4.0/documentation/validation.json) distinguishes post-publication tests from the immutable release snapshot.
