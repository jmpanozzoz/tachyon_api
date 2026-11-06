# Choosing Tachyon for a service

Evaluate Tachyon when its documented msgspec models, decorators and explicit DI
lifetimes fit your service, and a small ASGI implementation is useful to your team.
Check model/OpenAPI support, middleware and dependency versions before migrating.
It is not a drop-in FastAPI replacement; ecosystem compatibility and operational
history must be assessed for the actual integration.

Use the published stable version for evaluations that require a published
artifact. The development reference and its resource/CLI capabilities require the
matching development candidate. Do not describe development behavior as shipped
in 1.4.3. Performance data is scenario-, version- and hardware-specific; the
[1.4.3 comparison](../audits/1.4.3/fastapi-benchmark.md) is not a production SLA.

Start with the [reference application](../../example/README.md), then a bounded
[pilot](pilot-template.md). Assess onboarding, auth/transaction correctness,
latency, resources, deploy/recovery and maintenance effort. A database-heavy
application may see little of a framework-only throughput difference. A critical
service needs its own operating evidence and support arrangements.

License is GPL-3.0-or-later. Review the project's actual license and your
organization's requirements as part of choosing a dependency.
