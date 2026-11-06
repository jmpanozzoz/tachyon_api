# Support and compatibility policy

The latest published stable release is the default target for bug fixes.
Development candidates are explicitly labelled and are not recommendations for
critical deployment. There is no promised LTS branch or automatic backport window.
Breaking public behavior requires a migration note and an appropriate version;
existing CLI commands stay compatible unless a deprecation/migration is documented.

Python 3.10–3.13 is the declared interpreter range. Compatibility with a platform
is backed by dated execution records, not by a portable wheel or a configured CI
matrix. The 1.4.3 publication ran on macOS ARM64. New Linux and development
candidate results must identify their actual revision, artifact and interpreters.
Windows execution remains unverified until recorded separately.

Support is maintainer/community support with no response-time or availability
guarantee. Bug reports should include installed versions, platform, a minimal
reproduction, expected/actual behavior and sanitized logs. Use the
[security policy](../../SECURITY.md) for confidential reports.

Tachyon supports its documented OpenAPI subset and Python API. It does not promise
drop-in FastAPI compatibility, arbitrary ecosystem integration or a universal
performance multiplier. Application auth, migrations, durable jobs, storage and
operational SLOs remain application responsibilities. The reference application
demonstrates integrations without making them core runtime dependencies.

License remains GPL-3.0-or-later. This policy does not change its terms or promise
separate commercial licensing or legal advice.
