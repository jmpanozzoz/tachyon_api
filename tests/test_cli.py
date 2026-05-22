"""
Tests for Tachyon CLI.
"""

import tempfile
from pathlib import Path
from typer.testing import CliRunner

from tachyon_api.cli import app

runner = CliRunner()


class TestNewCommand:
    def test_new_creates_project_structure(self):
        # `my-api` is normalised to `my_api` by `validate_name` (hyphens → underscores)
        # so the project gets created under that Python-identifier-safe name.
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["new", "my-api", "--path", tmpdir])

            assert result.exit_code == 0
            assert "Creating Tachyon project" in result.stdout
            assert "my-api" in result.stdout and "my_api" in result.stdout

            project_path = Path(tmpdir) / "my_api"

            # Check directories
            assert (project_path / "modules").exists()
            assert (project_path / "shared").exists()
            assert (project_path / "tests").exists()

            # Check files
            assert (project_path / "app.py").exists()
            assert (project_path / "config.py").exists()
            assert (project_path / "requirements.txt").exists()
            assert (project_path / "shared" / "exceptions.py").exists()
            assert (project_path / "shared" / "dependencies.py").exists()
            assert (project_path / "tests" / "conftest.py").exists()

    def test_new_fails_if_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project once
            runner.invoke(app, ["new", "existing", "--path", tmpdir])

            # Try to create again
            result = runner.invoke(app, ["new", "existing", "--path", tmpdir])

            assert result.exit_code == 1
            assert "already exists" in result.stdout


class TestGenerateCommand:
    def test_generate_service_creates_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modules_path = Path(tmpdir) / "modules"
            modules_path.mkdir()

            result = runner.invoke(
                app, ["generate", "service", "auth", "--path", str(modules_path)]
            )

            assert result.exit_code == 0
            assert "Generating service" in result.stdout

            service_path = modules_path / "auth"

            # Check all files created
            assert (service_path / "__init__.py").exists()
            assert (service_path / "auth_controller.py").exists()
            assert (service_path / "auth_service.py").exists()
            assert (service_path / "auth_repository.py").exists()
            assert (service_path / "auth_dto.py").exists()
            assert (service_path / "tests" / "test_auth_service.py").exists()

    def test_generate_service_with_crud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modules_path = Path(tmpdir) / "modules"
            modules_path.mkdir()

            result = runner.invoke(
                app,
                [
                    "generate",
                    "service",
                    "products",
                    "--path",
                    str(modules_path),
                    "--crud",
                ],
            )

            assert result.exit_code == 0

            controller_path = modules_path / "products" / "products_controller.py"
            content = controller_path.read_text()

            # Should have CRUD endpoints
            assert "def list_products" in content
            assert "def get_product" in content
            assert "def create_product" in content
            assert "def update_product" in content
            assert "def delete_product" in content

    def test_generate_service_no_tests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modules_path = Path(tmpdir) / "modules"
            modules_path.mkdir()

            result = runner.invoke(
                app,
                [
                    "generate",
                    "service",
                    "users",
                    "--path",
                    str(modules_path),
                    "--no-tests",
                ],
            )

            assert result.exit_code == 0

            service_path = modules_path / "users"
            assert (service_path / "users_controller.py").exists()
            assert not (service_path / "tests" / "test_users_service.py").exists()

    def test_generate_controller_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app, ["generate", "controller", "items", "--path", tmpdir]
            )

            assert result.exit_code == 0
            assert (Path(tmpdir) / "items_controller.py").exists()

    def test_generate_repository_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app, ["generate", "repository", "items", "--path", tmpdir]
            )

            assert result.exit_code == 0
            assert (Path(tmpdir) / "items_repository.py").exists()

    def test_generate_dto_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["generate", "dto", "items", "--path", tmpdir])

            assert result.exit_code == 0
            assert (Path(tmpdir) / "items_dto.py").exists()

    def test_generate_converts_kebab_to_snake(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            modules_path = Path(tmpdir) / "modules"
            modules_path.mkdir()

            result = runner.invoke(
                app,
                ["generate", "service", "user-profile", "--path", str(modules_path)],
            )

            assert result.exit_code == 0

            # Should use snake_case
            service_path = modules_path / "user_profile"
            assert service_path.exists()
            assert (service_path / "user_profile_controller.py").exists()


class TestVersionCommand:
    def test_version_shows_version(self):
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Tachyon" in result.stdout


class TestLintCommand:
    def test_lint_check_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple Python file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")

            result = runner.invoke(app, ["lint", "check", tmpdir])

            # Exit code depends on whether ruff is installed and file issues
            # We just check it runs without crashing
            assert result.exit_code in [0, 1]


class TestOpenAPICommand:
    def test_openapi_validate_valid_schema(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "openapi.json"
            schema = {
                "openapi": "3.0.0",
                "info": {"title": "Test API", "version": "1.0.0"},
                "paths": {},
            }
            schema_path.write_text(json.dumps(schema))

            result = runner.invoke(app, ["openapi", "validate", str(schema_path)])

            assert result.exit_code == 0
            assert "valid" in result.stdout.lower()

    def test_openapi_validate_invalid_schema(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            schema_path = Path(tmpdir) / "openapi.json"
            schema = {"invalid": "schema"}
            schema_path.write_text(json.dumps(schema))

            result = runner.invoke(app, ["openapi", "validate", str(schema_path)])

            assert result.exit_code == 1
            assert "missing" in result.stdout.lower()
