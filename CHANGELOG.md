# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.2] - 2025-08-06

### Fixed

- **OpenAPI Documentation:** Fixed Scalar API Reference implementation.
  - Resolved issue where the Scalar UI failed to load properly at the `/docs` endpoint
  - Improved HTML structure of documentation to remove malformed elements
  - Fixed Scalar script URL to ensure proper component loading

### Added

- **Documentation Testing:** New unit test to verify proper HTML generation for Scalar API Reference.
  - Implemented `test_scalar_html_generation()` that validates the correct structure of generated HTML
  - Ensures compatibility between all three documentation interfaces: Scalar (default), Swagger UI, and ReDoc

### Technical Improvements

- **Documentation Consistency:** Ensured consistency between all three available documentation interfaces
  - Scalar API Reference: available at `/docs` (default)
  - Swagger UI: maintains compatibility for integration with existing tools
  - ReDoc: available as an alternative at `/redoc`

---

## [0.4.1] - 2025-08-05

### Changed

- **Example Application Refactoring:** Complete reorganization of the example application using clean architecture principles.
  - Restructured `/example` directory with proper separation of concerns
  - Added `/example/routers/` directory for organized API endpoint management
  - Enhanced `/example/repositories/` with proper dependency injection setup
  - Improved `/example/services/` to demonstrate implicit dependency injection
  - Updated `/example/models/` with comprehensive data structures

### Added

- **Router Organization:** New router-based architecture in example application.
  - `users_router`: Complete user management endpoints (`/api/v1/users/*`)
  - `items_router`: Item management endpoints (`/api/v1/items/*`)
  - `admin_router`: Administrative endpoints (`/admin/*`)

### Technical Improvements

- **Clean Architecture Demonstration:** Example now showcases proper layered architecture:
  - Models: Data structures and validation
  - Repositories: Data access layer with `@injectable` decorators
  - Services: Business logic layer with automatic dependency resolution
  - Routers: API endpoint organization with implicit dependency injection
- **Enhanced Documentation:** Updated example application with comprehensive inline documentation
- **Implicit Dependency Injection:** Example demonstrates parameter ordering for maximum use of implicit DI

---

## [0.4.0] - 2025-08-05

### Added

- **Router System:** Complete route grouping functionality similar to FastAPI's APIRouter.
  - Create routers with common prefixes, tags, and dependencies
  - Include multiple routers in the main application with `app.include_router()`
  - Automatic prefix application to all routes in a router
  - Tag inheritance from router to individual routes
  - Full compatibility with existing parameter types (Query, Path, Body) and dependency injection
  - OpenAPI integration with proper route documentation

- **Scalar API Reference Integration:** Modern API documentation interface as default.
  - `/docs` now serves Scalar API Reference (modern, fast UI)
  - `/swagger` continues to serve Swagger UI (legacy support)
  - `/redoc` unchanged, continues to serve ReDoc
  - Configurable Scalar CDN URLs and styling options
  - Backward compatibility maintained for all existing OpenAPI configurations

### Changed

- **Documentation Default:** `/docs` endpoint now uses Scalar instead of Swagger UI by default
- **Route Organization:** Enhanced route organization capabilities with Router system

### Technical Details

- Router implementation follows TDD approach with comprehensive test coverage
- Zero code redundancy - Router reuses existing Tachyon routing logic
- 100% backward compatibility with existing applications
- Router stores route definitions and delegates actual routing to main Tachyon app

---

## [0.3.1] - 2025-08-04

### Added

- **Complete Example Application:** A full example project has been added in the `/example` directory.
- The example demonstrates a real-world use case with a complete `users` service, showcasing:
    - The recommended project structure.
    - Usage of the Service and Repository patterns.
    - Implementation of various endpoints using `@Body`, `@Query`, `@Path`, and Dependency Injection.
- This application serves as a reference for new users and as a basis for tutorials and training materials.

---

## [0.3.0] - 2025-08-04

### Added

- **Structured Response Helpers:** A new `responses.py` module was introduced to provide a consistent API output
  structure.
    - Includes `success_response` for standardized success payloads (`{"success": true, "data": ..., "message": ...}`).
    - Includes `error_response`, `not_found_response`, `conflict_response`, and `validation_error_response` for
      standardized error payloads.
- **Centralized Starlette Responses:** Re-exported core `starlette.responses` (`JSONResponse`, `HTMLResponse`) from
  `tachyon_api.responses` to centralize imports for the end-user.

---

## [0.2.1] - 2025-08-04

### Added

- **Parameter Documentation:** The `Query()` and `Path()` parameter markers now accept a `description` argument.
- **Enhanced OpenAPI Generation:** The OpenAPI schema generator now includes these descriptions, leading to richer and
  more descriptive API documentation.

---

## [0.2.0] - 2025-08-04

### Added

- **Automatic OpenAPI 3.0 Schema Generation:** The framework now introspects routes, parameters (`Path`, `Query`,
  `Body`), and models (`Struct`) to generate a compliant `openapi.json`.
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
    - `@Query()` decorator for query parameter extraction, type conversion, and validation (required and default
      values).
    - `@Path()` decorator for path parameter extraction and type conversion.
- **Centralized Test Fixture:** A project-wide `app` fixture in `conftest.py` to streamline testing.

### Changed

- Refactored parameter resolution logic out of the main request handler into dedicated helper functions for improved
  maintainability.

---

## [0.0.1] - 2025-07-21

### Added

- **Core Application:** Initial `Tachyon` ASGI application class.
- **Dynamic Routing:** Support for all standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`, etc.) via dynamic
  decorator generation.
- **Basic Project Structure:** Initial setup using Poetry.
- **Testing Foundation:** Integrated `pytest` and `httpx` for Test-Driven Development.
- **Code Quality:** Integrated `ruff` for code linting and formatting.
- **Model Abstraction:** Re-exported `msgspec.Struct` as `tachyon_api.models.Struct` to create a stable public API for
  users.