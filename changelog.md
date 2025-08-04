# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2025-08-04

### Added
- **Automatic OpenAPI 3.0 Schema Generation:** The framework now introspects routes, parameters (`Path`, `Query`, `Body`), and models (`Struct`) to generate a compliant `openapi.json`.
- **Interactive API Documentation:** Added a `/docs` endpoint that serves a fully interactive Swagger UI.
- `include_in_schema` option for routes to exclude specific endpoints from the OpenAPI documentation.

---

## [0.1.0] - 2025-07-28

### Added
- **Dependency Injection System:**
    - `@injectable` decorator to register classes with the DI container.
    - Hybrid injection support for endpoints:
        - Implicitly for parameters with a registered type hint and no default value.
        - Explicitly via a `Depends()` marker for FastAPI compatibility and clarity.
    - Constructor injection for nested dependencies within `@injectable` classes.
- **Parameter Validation & Extraction:**
    - `@Body()` decorator for request body validation using `msgspec.Struct`.
    - `@Query()` decorator for query parameter extraction, type conversion, and validation (required and default values).
    - `@Path()` decorator for path parameter extraction and type conversion.
- **Centralized Test Fixture:** A project-wide `app` fixture in `conftest.py` to streamline testing.

### Changed
- Refactored parameter resolution logic out of the main request handler into dedicated helper functions for improved maintainability.

---

## [0.0.1] - 2025-07-21

### Added
- **Core Application:** Initial `Tachyon` ASGI application class.
- **Dynamic Routing:** Support for all standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, etc.) via dynamic decorator generation.
- **Basic Project Structure:** Initial setup using Poetry.
- **Testing Foundation:** Integrated `pytest` and `httpx` for Test-Driven Development.
- **Code Quality:** Integrated `ruff` for code linting and formatting.
- **Model Abstraction:** Re-exported `msgspec.Struct` as `tachyon_api.models.Struct` to create a stable public API for users.