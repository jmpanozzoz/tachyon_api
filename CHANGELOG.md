# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.0] - 2025-12-12

### ♻️ Refactored - Major Architecture Improvements

This release focuses on **code quality, maintainability, and separation of concerns** through systematic refactoring of the core `Tachyon` class.

#### Code Reduction
- **Reduced `app.py` from ~1157 lines to ~700 lines (-39%)** 🎯
- Extracted complex logic into dedicated, single-responsibility modules
- Improved testability and maintainability

#### New Architecture Modules

**Core Components** (`tachyon_api/core/`)
- `lifecycle.py` - Application lifecycle event management (startup/shutdown)
- `websocket.py` - WebSocket route handling and parameter injection

**Processing Components** (`tachyon_api/processing/`)
- `parameters.py` - Parameter extraction and validation (Path, Query, Body, Header, Cookie, Form, File)
- `dependencies.py` - Dependency injection resolution (injectable classes and Depends())
- `response_processor.py` - Response validation, serialization, and background task execution

#### Key Improvements
- ✅ **All 223 tests passing** - Zero regressions
- ✅ **Clean code** - Ruff linter passing on all modules
- ✅ **DRY principles** - Eliminated code duplication
- ✅ **Better separation of concerns** - Each module has a single, clear responsibility
- ✅ **Improved documentation** - All new modules fully documented
- ✅ **Type safety** - Maintained strong typing throughout

#### Technical Details
- Extracted `LifecycleManager` for managing startup/shutdown hooks and `@app.on_event` decorators
- Extracted `WebSocketManager` for WebSocket route registration and path parameter injection
- Extracted `ParameterProcessor` for all parameter types (Request, BackgroundTasks, Dependencies, Body, Query, Header, Cookie, Form, File, Path)
- Extracted `DependencyResolver` for both type-based (@injectable) and callable (Depends()) dependency injection
- Extracted `ResponseProcessor` for endpoint execution, response validation, and background task running

#### Migration Notes
- **No breaking changes** - All public APIs remain unchanged
- Internal refactoring only - fully backward compatible
- Imports remain the same: `from tachyon_api import Tachyon, Struct, Body, ...`

### Testing
- **223/223 tests passing** ✅
- All existing functionality verified
- No performance degradation

---

## [0.7.0] - 2025-12-12

### Added

- **WebSocket Support**: Real-time bidirectional communication
  - `@app.websocket(path)` decorator for WebSocket endpoints
  - `@router.websocket(path)` for WebSocket routes in routers
  - Path and query parameter support in WebSocket routes
  - Text, JSON, and binary message handling
  - Automatic injection of WebSocket object into handler functions

- **Complete Documentation**: 16 comprehensive guides in `docs/`
  - Getting Started, Architecture, Dependency Injection
  - Parameters, Validation, Security
  - Caching, Lifecycle Events, Background Tasks
  - WebSockets, Testing, CLI Tools
  - Request Lifecycle, FastAPI Migration, Best Practices

- **KYC Demo Example**: Production-ready example in `example/`
  - Complete Know Your Customer verification system
  - JWT authentication with `@injectable` services
  - Customer CRUD with clean architecture
  - Document uploads with validation
  - Background task processing for verification
  - WebSocket notifications for real-time updates
  - 12 tests demonstrating mocking and dependency overrides

### Changed

- Example project completely rewritten from simple CRUD to comprehensive KYC system
- README updated with feature matrix and documentation links
- Version badge updated to 0.7.0

### Tests

- 12 new tests for WebSockets (223 → 235 total)
  - Basic echo, JSON/binary messages, path/query params
  - Router integration, multiple routes, disconnect handling
- 12 new tests for KYC example
  - Authentication, customers, verification modules

---

## [0.6.7] - 2025-12-12

### Added

- **Testing Utilities**: Comprehensive testing support
  - `TachyonTestClient`: Synchronous test client wrapping `starlette.testclient.TestClient`
  - `AsyncTachyonTestClient`: Asynchronous test client with `httpx.AsyncClient` and `ASGITransport`
  - `app.dependency_overrides`: Dictionary for mocking dependencies in tests
  - Supports overriding `@injectable` classes and `Depends()` callables

### Tests

- 12 new tests for testing utilities (211 → 223 total)
  - TachyonTestClient (GET/POST, headers, query, cookies, context manager)
  - AsyncTachyonTestClient (async GET/POST)
  - dependency_overrides (classes, callables, lambdas, multiple overrides)

---

## [0.6.6] - 2025-12-12

### Added

- **CLI Tools**: NestJS-inspired command-line interface
  - `tachyon new <project>`: Scaffold new project with clean architecture
  - `tachyon generate service <name>`: Generate complete module (controller, service, repository, dto, tests)
  - `tachyon generate controller/repository/dto`: Generate individual components
  - `tachyon openapi export`: Export OpenAPI schema to JSON
  - `tachyon openapi validate`: Validate OpenAPI schema files
  - `tachyon lint check/fix/format/all`: Code quality tools (ruff wrapper)
  - Project scaffolding includes: app.py, config.py, modules/, shared/, tests/
  - `--crud` flag for generating CRUD operations
  - `--no-tests` flag to skip test generation

### Changed

- Added `[tool.poetry.scripts]` entry point: `tachyon = "tachyon_api.cli:app"`

### Tests

- 13 new tests for CLI (198 → 211 total)
  - Project creation, existing directory handling
  - Service generation (basic, CRUD, no-tests, individual components)
  - Kebab-case conversion (user-profile → user_profile)
  - Version command, lint check, openapi validate

---

## [0.6.5] - 2025-12-12

### Added

- **Background Tasks**: Fire-and-forget task execution after response
  - `BackgroundTasks` class with `add_task(func, *args, **kwargs)` method
  - Automatic injection when `background_tasks: BackgroundTasks` parameter present
  - Supports sync and async functions
  - Error handling: failed tasks don't affect response
  - Tasks execute in order after response is sent

### Tests

- 6 new tests for background tasks (192 → 198 total)
  - Basic sync/async tasks
  - Multiple tasks, keyword arguments
  - Coexistence with other parameters
  - Error handling in tasks

---

## [0.6.4] - 2025-12-12

### Added

- **Security Foundation**: Authentication and authorization schemes
  - `HTTPBearer`: Extract Bearer token from Authorization header
  - `HTTPBasic`: Extract and decode Basic auth credentials
  - `OAuth2PasswordBearer`: OAuth2 password flow with configurable token URL
  - `APIKeyHeader`, `APIKeyQuery`, `APIKeyCookie`: API key extraction
  - All schemes support `auto_error=False` for optional authentication
  - Credential classes: `HTTPAuthorizationCredentials`, `HTTPBasicCredentials`
  - All security schemes are callable dependencies compatible with `Depends()`

### Tests

- 12 new tests for security (180 → 192 total)
  - HTTPBearer (valid/missing/invalid token, auto_error=False)
  - HTTPBasic (valid/missing credentials, base64 decoding)
  - API Keys (header, query, cookie)
  - OAuth2PasswordBearer (valid/missing token)

---

## [0.6.3] - 2025-12-12

### Added

- **Exception Handling System**: Custom exceptions and handlers
  - `HTTPException` class with `status_code`, `detail`, and optional `headers`
  - `@app.exception_handler(ExceptionClass)` decorator for custom handlers
  - Supports sync and async exception handlers
  - Request object injection in handlers via `request: Request` parameter
  - Multiple exception handlers for different exception types
  - Allows overriding default `HTTPException` handler

### Tests

- 11 new tests for exception handling (169 → 180 total)
  - Basic HTTPException (401, 403, 500, custom headers)
  - Custom exception handler decorator
  - Sync/async handlers
  - Request injection into handlers
  - Multiple handlers, overriding HTTPException handler
  - Unhandled exceptions fallback

---

## [0.6.2] - 2025-12-12

### Added

- **File Handling**: Form data and file uploads
  - `Form()` parameter marker for `application/x-www-form-urlencoded` data
  - `File()` parameter marker for `multipart/form-data` uploads
  - `UploadFile` class wrapping Starlette's UploadFile
  - Support for multiple file uploads (List[UploadFile])
  - Mixed form data and file uploads in same endpoint
  - Async file operations (read, seek, close)
  - Dependency: `python-multipart` for form parsing

### Tests

- 8 new tests for file handling (161 → 169 total)
  - Form data parsing (single, multiple fields)
  - File uploads (single, multiple, optional)
  - Mixed form + file
  - UploadFile properties (filename, content_type, size)

---

## [0.6.1] - 2025-12-12

### Added

- **Lifecycle Events**: Application startup and shutdown hooks
  - `lifespan` context manager parameter in `Tachyon.__init__`
  - `@app.on_event("startup")` decorator for startup tasks
  - `@app.on_event("shutdown")` decorator for shutdown tasks
  - Supports both sync and async event handlers
  - `app.state` for storing application-wide state
  - Combined lifespan merging decorator-based and context manager events

### Tests

- 17 new tests for lifecycle (144 → 161 total)
  - Lifespan context manager (startup/shutdown execution)
  - on_event decorators (sync/async)
  - app.state usage
  - Combined lifespan + on_event
  - Execution order verification

---

## [0.6.0] - 2025-12-11

### Added

- **Request Injection**: Endpoints can now receive the Starlette `Request` object by annotating a parameter with `request: Request`
  - Access to headers, query params, cookies, client info, and raw request data
  - Works alongside other parameter types (Query, Path, Body, etc.)

- **Header() Parameter Marker**: Extract values from HTTP request headers
  - Required headers: `Header(...)` returns 422 if missing
  - Optional with default: `Header("default-value")`
  - Case-insensitive matching (HTTP standard)
  - Underscore-to-hyphen conversion: `x_request_id` matches `X-Request-Id`
  - Custom header names with alias: `Header(..., alias="X-Auth-Token")`
  - Full OpenAPI schema generation for header parameters

- **Cookie() Parameter Marker**: Extract values from HTTP cookies
  - Required cookies: `Cookie(...)` returns 422 if missing
  - Optional with default: `Cookie("default-value")`
  - Custom cookie names with alias: `Cookie(..., alias="session_token")`
  - Full OpenAPI schema generation for cookie parameters

- **Depends(callable) - Factory Dependencies**: Enhanced dependency injection
  - Sync function dependencies: `Depends(get_db_connection)`
  - Async function dependencies: `Depends(get_current_user_async)`
  - Lambda dependencies: `Depends(lambda: {"config": "value"})`
  - Nested dependencies: callables can have their own `Depends()` parameters
  - Per-request caching: same callable called once per request
  - Works alongside existing `Depends()` type-based resolution

### Changed

- **Refactored Type Utilities**: Centralized type handling to reduce code duplication
  - `OPENAPI_TYPE_MAP` in `type_utils.py` as single source of truth
  - `TypeUtils.get_openapi_type()` for type-to-schema conversion
  - Removed duplicate `_unwrap_optional` and `TYPE_MAP` from `openapi.py`
  - Removed dead code: `_generate_schema_for_struct`

### Tests

- 25 new tests (119 → 144 total)
  - `test_request_injection.py`: 5 tests
  - `test_header_params.py`: 8 tests
  - `test_cookie_params.py`: 5 tests
  - `test_depends_callable.py`: 7 tests

---

## [0.5.9] - 2025-09-04

### Added

- Tests: new utility test suite in `tests/test_utils.py`
  - TypeUtils: `unwrap_optional`, `is_list_type`, `get_type_name`
  - TypeConverter: `convert_value` (str, int, bool, Optional) and `convert_list_values` (including Optional items)
  - Error mapping verification: 422 for invalid query values and 404 for invalid path values

### Changed

- Refactor: extracted and modularized utility helpers previously located in `app.py`
  - New modules: `tachyon_api/utils/type_utils.py` and `tachyon_api/utils/type_converter.py`
  - No intended runtime behavior changes; improves separation of concerns and reuse

---

## [0.5.8] - 2025-08-26

### Added

- Global Exception Handler: structured 500 responses for unhandled exceptions
  - Returns `{ "success": false, "error": "Internal Server Error", "code": "INTERNAL_SERVER_ERROR" }`
  - Prevents leaking internal exception details to clients
- Tests: Added `test_global_unhandled_exception_is_structured_500` (TDD)
- Documentation: README updated (error section) and example endpoint `/error-demo`

---

## [0.5.7] - 2025-08-26

### Added

- Response Model Validation: `response_model` in route decorators to enforce and serialize outputs via msgspec
  - Converts handler payloads to the specified Struct type; 500 on response validation error
  - OpenAPI 200 response schema references the Struct component
- OpenAPI Parameters: Enhanced schema generation for Optional and List parameter types
  - Optional[T] → `nullable: true` on the base type schema
  - List[T] → `type: array` with proper `items` schema in both query and path parameters
  - List[Optional[T]] → `items.nullable: true`
- Default JSON Response: `TachyonJSONResponse` is now used by default for dict/Struct payloads
  - orjson-based, supports UUID, date, datetime and msgspec Struct out of the box
- Deep OpenAPI Schemas for Struct
  - Nested Struct components auto-registered and referenced
  - Field Optional/List handling with `nullable` and `array/items`
  - Type formats for `uuid` and `date-time`/`date`
- Standard Error Schemas in OpenAPI
  - 422 Validation Error → `#/components/schemas/ValidationErrorResponse`
  - 500 Response Validation Error → `#/components/schemas/ResponseValidationError`

### Changed

- Error Format Unification: standardized error payloads for validation and response errors
  - 422 (request validation) → `{ "success": false, "error": "...", "code": "VALIDATION_ERROR" }`
  - 500 (response_model validation) → `{ "success": false, "error": "Response validation error: ...", "detail": "...", "code": "RESPONSE_VALIDATION_ERROR" }`

### Fixed

- Query list parsing accepts both CSV (`?ids=1,2,3`) and repeated params (`?ids=1&ids=2`)
- Runtime support for `List[Optional[T]]` in Query and Path
  - Empty string "" and literal "null" are treated as `None` when item type is Optional

### Example

- Added `/api/v1/users/e2e` endpoint demonstrating end-to-end safety (Body + response_model), unified errors, and deep OpenAPI schemas.

---

## [0.5.6] - 2025-08-26

### Added

- Cache Decorator with TTL (`tachyon_api.cache.cache`)
  - Works with sync and async functions, including route handlers
  - Global, app-level configuration via `create_cache_config()` and `Tachyon(cache_config=...)`
  - Pluggable backends: `InMemoryCacheBackend` (default), `RedisCacheBackend`, `MemcachedCacheBackend`
  - Customizable `key_builder` and `unless` predicate
- Tests: New `tests/test_cache_decorator.py` validating caching behavior, TTL, async support, and config integration
- Example: Added cached endpoint `/cached/time` and cache configuration in `example/app.py`

### Changed

- App: `Tachyon` now accepts `cache_config` and applies it on initialization (backwards compatible)
- Documentation: README updated with cache section, quick start, configuration, and backend usage
- Language Consistency: Standardized remaining comments/docstrings to English across touched files

### Notes

- Redis/Memcached backends are lightweight adapters; bring your own client instance. No hard dependencies added.

---

## [0.5.5] - 2025-08-12

### Added

- Built-in Middlewares: CORSMiddleware and LoggerMiddleware
  - Standard ASGI-compatible classes usable via `app.add_middleware(...)`
  - CORS: preflight handling, allow/expose headers, credentials, max-age
  - Logger: request start/end, duration, status; optional headers and body preview with redaction
- Tests: Added `tests/test_cors_middleware.py` and `tests/test_logger_middleware.py`
- Example: Integrated built-in middlewares in `example/app.py`

### Changed

- Middleware Refactor: centralized integration helpers in `tachyon_api/middlewares/core.py`
  - `apply_middleware_to_router()` for Starlette stack integration
  - `create_decorated_middleware_class()` for decorator-based middlewares
  - Maintained full backward compatibility for `app.add_middleware` and `@app.middleware()`
- Language Consistency: standardize docstrings and comments to English in middleware modules and tests
- Documentation: README updated with built-in middleware usage and example details

---

## [0.5.4] - 2025-08-06

### Added

- **Comprehensive README**: Created a detailed README.md for the project.
  - Comprehensive feature overview and code examples
  - Clear installation instructions for the beta version
  - Feature comparison with FastAPI
  - Detailed examples of dependency injection and middleware usage
  - Expanded roadmap with upcoming features
  - Contributor guidelines and project structure explanation

### Technical Improvements

- **Project Documentation**: Enhanced project presentation for the upcoming GitHub beta release
- **Onboarding Experience**: Clearer instructions for new users and contributors
- **Framework Positioning**: Better articulation of Tachyon API's unique value proposition

---

## [0.5.3] - 2025-08-06

### Added

- **Traditional Python Environment Support:** Added requirements.txt for broader compatibility.
  - Support for traditional venv-based workflows alongside Poetry
  - Direct pip installation capability via `pip install -r requirements.txt`
  - Maintained synchronization between Poetry dependencies and requirements.txt

### Technical Improvements

- **Deployment Flexibility:** Support for environments where Poetry isn't available
- **CI/CD Compatibility:** Better integration with common CI/CD pipelines
- **Onboarding Experience:** Easier project setup for developers familiar with traditional Python workflows

---

## [0.5.2] - 2025-08-06

### Changed

- **Decoupled Test Architecture:** Refactored all tests to be self-contained.
  - Removed test dependencies on conftest.py fixture for better isolation
  - Each test now creates its own Tachyon instance with required configuration
  - Improved test clarity and maintenance by making test dependencies explicit
  - Fixed language consistency across all test files (standardized to English)

### Fixed

- **Response Module:** Added missing HTMLResponse export in responses.py
  - Resolved issue with TestStarletteCompatibility.test_starlette_imports_available test
  - Ensured proper re-export of all Starlette response types for convenience

### Technical Improvements

- **Testing Efficiency:** Self-contained tests provide better failure isolation and debugging
- **Test Clarity:** Each test file now clearly shows its dependencies and requirements
- **Consistent Documentation:** All code comments and docstrings standardized to English

---

## [0.5.1] - 2025-08-06

### Added

- **Example Middleware Implementation:** Enhanced example application with middleware examples.
  - Added request logging middleware to demonstrate request/response monitoring
  - Implemented response headers middleware to show response modification
  - Created a reusable middleware setup pattern in a dedicated module

### Technical Improvements

- **Middleware Organization:** Implemented a clean pattern for middleware definition in separate files
- **Middleware Documentation:** Comprehensive examples demonstrating middleware capabilities
- **Example Architecture:** Improved example application structure with middleware integration

---

## [0.5.0] - 2025-08-06

### Added

- **Middleware Support:** Added comprehensive middleware functionality.
  - Implemented `app.add_middleware()` method for adding middleware classes
  - Created `@app.middleware()` decorator for a more elegant middleware definition
  - Added support for both class-based and decorator-based middleware approaches
  - Full integration with the ASGI specification for compatibility with standard patterns

### Changed

- **Decorator API:** Enhanced the API with middleware decorators for better developer experience
  - Consistent pattern with route decorators like `@app.get()`, `@app.post()`, etc.
  - Support for middleware type filtering (`http`, etc.)

### Technical Improvements

- **Request/Response Pipeline:** Complete implementation of the middleware "onion" pattern
- **Testing Coverage:** Comprehensive test suite for middleware functionality
- **Architecture Flexibility:** Support for multiple middleware implementation styles

---

## [0.4.3] - 2025-08-06

### Added

- **orjson Integration:** Enhanced JSON processing with high-performance orjson library.
  - Added new `encode_json` and `decode_json` functions for direct access to optimized JSON operations
  - Implemented seamless serialization of complex types (UUID, datetime, etc.)
  - Maintained full backward compatibility with existing Struct-based models
  - Comprehensive test suite ensures correctness and performance improvements

### Technical Improvements

- **Performance Optimization:** JSON serialization/deserialization now significantly faster with orjson
- **Enhanced Type Support:** Better handling of complex types like UUID, datetime, and nested Struct objects
- **Flexible Configuration:** Support for orjson-specific options when using the explicit API

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