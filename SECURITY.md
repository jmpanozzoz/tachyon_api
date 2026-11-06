# Security policy

Report suspected vulnerabilities privately through the repository's GitHub
security advisory reporting if enabled, or contact the maintainer at
jm.panozzozenere@gmail.com. Include affected versions, a minimal reproduction,
impact and deployment assumptions. Do not send production secrets or personal data.
If private advisory reporting is unavailable, use email rather than a public issue.

The maintainer triages reports as capacity permits. There is no guaranteed
response time, paid support commitment or 24/7 response service. Acknowledgement,
workaround, fix and public disclosure timing are coordinated case by case.

The project targets fixes on the latest stable release. Older releases do not
have an automatic backport or long-term support commitment. Development builds
are not stable releases. See the [support policy](docs/quality/support-policy.md).

Dependencies have their own advisories and support policies. Operators should
track the resolved dependency versions and evaluate their deployment exposure.
Successful tests or a scanner finding no known advisories do not prove security.

The example uses a synthetic verification provider and synthetic test data. It
is not an identity verification service. Published 1.4.3 contains the earlier
in-memory example; improvements on development branches do not patch that tag.
