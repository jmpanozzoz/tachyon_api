# Tachyon API documentation

The current release is [1.4.3 on PyPI](https://pypi.org/project/tachyon-api/1.4.3/).
Python 3.10–3.13 is supported through one portable Python implementation and a
source distribution. Validation of the 1.4.3 release ran on macOS ARM64; Linux
and Windows execution of this release remain unverified. See
[release validation](audits/1.4.3/summary.json),
[publication receipt](audits/1.4.3/PUBLICATION.md),
[release notes](https://github.com/jmpanozzoz/tachyon_api/releases/tag/v1.4.3)
and the [changelog](../CHANGELOG.md). Third-party dependencies retain their own
native wheel/build requirements.

The current branch develops 1.5.0.dev0. New resource dependencies, persistent
reference and CLI additions require that candidate; they are not shipped in 1.4.3.

## Guides

| Guide | Scope |
| --- | --- |
| [01. Getting started](01-getting-started.md) | Installation and first application |
| [02. Architecture](02-architecture.md) | Project structure, controllers and services |
| [03. Dependency injection](03-dependency-injection.md) | Providers, scopes, overrides and lifetime restrictions |
| [04. Parameters](04-parameters.md) | Path, query, body, header, cookie, form and file inputs |
| [05. Validation](05-validation.md) | msgspec models, response models and errors |
| [06. Security](06-security.md) | Credential extraction and application authentication |
| [07. Caching](07-caching.md) | TTL, namespaces and external backend contracts |
| [08. Lifecycle](08-lifecycle.md) | Startup, shutdown and lifespan |
| [09. Background tasks](09-background-tasks.md) | Execution after transmission and resource ownership |
| [10. WebSockets](10-websockets.md) | Connections, paths and supported injection |
| [11. Testing](11-testing.md) | Sync/async clients, overrides and lifespan |
| [12. CLI](12-cli.md) | Scaffolding, inspection and development tools |
| [13. Request lifecycle](13-request-lifecycle.md) | Registration, dispatch, validation and cleanup |
| [14. FastAPI migration](14-migration-fastapi.md) | API and execution differences |
| [15. Best practices](15-best-practices.md) | Application design and deployment considerations |
| [16. Portable builds](16-cython-build.md) | Python packaging, installed checks and upgrade from Cython |
| [17. Migration to 1.4](17-migration-1.4.md) | Changed behavior and explicit limitations |

## Start an application

```python
from tachyon_api import Body, Struct, Tachyon

app = Tachyon()

class User(Struct):
    name: str
    email: str

@app.post("/users", response_model=User)
async def create_user(user: User = Body()):
    return user
```

Save as `app.py`, install `tachyon-api`, then run `uvicorn app:app --reload`.
Interactive documentation is available at `/docs`.

## Verification and maintenance

- [Executable example](../example/README.md): demonstration application and test scope.
- [Benchmark methodology](../benchmark/README.md): validated measurements and limits.
- [Continuous improvement](quality/continuous-improvement.md): repair/review gates.
- [Framework assessment](quality/framework-review.md): maintainability, production limits, refreshed FastAPI measurements, Cython removal experiments and Rust research dated 2026-11-04.
- [Local release](quality/local-release.md): builds and publication without Actions.
- [1.4.3 simplification](audits/1.4.3/README.md): implementation decisions and candidate validation.
- [Production and adoption plan](quality/production-readiness.md): request resource cleanup, Linux validation, the reference demo, CLI improvements, maintenance and pilots. Proposed work, not completed capabilities.
- [Linux validation](quality/linux-validation.md): inventory, installed checks, business load and explicit pending execution.
- [Operations](quality/operations-runbook.md), [support policy](quality/support-policy.md) and [dependency compatibility](quality/dependency-compatibility.md).
- [Adoption](adoption/choosing-tachyon.md) and [pilot record](adoption/pilot-template.md).
- [Documentation maintenance](quality/documentation.md): source comparisons, links and executable examples.
- [Historical audits](audits/1.4.0/AUDITORIA.md): dated findings with current-status links.

The framework uses Starlette ASGI integration, msgspec validation, a radix trie
and bounded request/cache behavior. Version 1.4.3 uses one Python implementation. The
supported OpenAPI subset and API differences are described in the migration
guides. Performance results are workload-specific; no universal multiplier or
competitor dependency-count comparison is asserted.

License: GPL-3.0-or-later.
