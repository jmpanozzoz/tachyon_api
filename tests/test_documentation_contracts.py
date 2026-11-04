"""Executable contracts for user-facing Python documentation and scaffolding.

All Python fences are parsed/compiled. Contextual fragments intentionally keep
application collaborators as placeholders; standalone guides run real requests.
"""

import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import types
from urllib.parse import unquote, urlsplit

import pytest
from typer.testing import CliRunner

from tachyon_api.cli.main import app as cli
from tachyon_api.testing import TachyonTestClient

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "example/README.md"]
FENCES = re.compile(r"^```python[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
BLOCKS = [(path, index, match[1]) for path in DOCS for index, match in enumerate(FENCES.finditer(path.read_text()))]


@pytest.mark.parametrize("path", [*DOCS, ROOT / "CLAUDE.md", ROOT / "benchmark/README.md", *sorted((ROOT / "docs/quality").glob("*.md"))], ids=lambda path: str(path.relative_to(ROOT)))
def test_maintained_documentation_links_resolve_locally(path):
    # External services and historical audit references need separate review.
    for match in re.finditer(r"\[[^\]]*\]\(([^\s)]+)\)", path.read_text()):
        target = match[1].strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved = (path.parent / unquote(parsed.path)).resolve()
        assert resolved.exists(), f"{path.relative_to(ROOT)}: broken link {target}"


@pytest.mark.parametrize("path,index,source", BLOCKS, ids=[f"{path.relative_to(ROOT)}:{index}" for path, index, _ in BLOCKS])
def test_python_documentation_blocks_compile_and_use_current_markers(path, index, source):
    tree = ast.parse(source, filename=f"{path}:{index}")
    compile(tree, str(path), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else None
        keywords = {kw.arg for kw in node.keywords}
        if name in {"Body", "Path", "Query"}:
            assert "alias" not in keywords, (path, index, name)
        if name == "Path":
            assert not (node.args and "description" in keywords), (path, index)
        if name == "cache":
            assert "ttl" not in keywords, (path, index)


def load_block(relative, index):
    path = ROOT / relative
    source = list(FENCES.finditer(path.read_text()))[index][1]
    name = f"_tachyon_doc_{relative.replace('/', '_').replace('.', '_')}_{index}"
    module = types.ModuleType(name)
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def test_getting_started_crud_is_executable():
    source = next(index for path, index, text in BLOCKS if path.name == "01-getting-started.md" and "items_db = {}" in text)
    module = load_block("docs/01-getting-started.md", source)
    with TachyonTestClient(module.app) as client:
        created = client.post("/items", json={"name": "book", "price": 12.5})
        assert created.status_code == 200
        item = created.json()
        assert item["name"] == "book"
        assert client.get(f"/items/{item['id']}").json() == item
        assert client.get("/items").json()["total"] == 1
        assert client.post("/items", json={"name": "bad", "price": "invalid"}).status_code == 422
        assert client.delete(f"/items/{item['id']}").json() == {"deleted": True}
        assert client.get(f"/items/{item['id']}").status_code == 404


@pytest.mark.parametrize("index,method,url,kwargs,expected", [
    (0, "get", "/items/example", {}, {"item_id": "example"}),
    (1, "get", "/tags?tags=a,b&tags=c", {}, {"tags": ["a", "b", "c"]}),
    (2, "post", "/users", {"json": {"name": "Ada", "email": "ada@example.com"}}, {"created": "Ada", "email": "ada@example.com"}),
    (3, "get", "/api", {"headers": {"X-API-Key": "demo"}}, {"api_key": "demo"}),
    (4, "get", "/preferences", {}, {"theme": "light"}),
    (5, "post", "/login", {"data": {"username": "Ada", "password": "demo"}}, {"username": "Ada"}),
    (6, "post", "/gallery", {"data": {"title": "Demo"}, "files": [("images", ("../one.txt", b"one")), ("images", ("two.txt", b"two"))]}, {"title": "Demo", "images": ["one.txt", "two.txt"]}),
    (7, "post", "/stores/demo/items?notify=true", {"headers": {"authorization": "Bearer demo"}, "json": {"name": "book", "price": 10}}, {"store": "demo", "item": "book", "notify": True, "auth": "Bearer demo..."}),
])
def test_parameter_guide_standalone_endpoints(index, method, url, kwargs, expected):
    module = load_block("docs/04-parameters.md", index)
    with TachyonTestClient(module.app) as client:
        response = getattr(client, method)(url, **kwargs)
    assert response.status_code == 200, response.text
    assert response.json() == expected


def test_architecture_layers_execute_together():
    # The guide deliberately splits relative-import modules. Assemble those
    # exact snippets into a package rather than replacing them with mocks.
    package = types.ModuleType("_tachyon_architecture")
    package.__path__ = []
    sys.modules[package.__name__] = package
    names = [(3, "users_dto"), (2, "users_repository"), (1, "users_service"), (0, "users_controller")]
    try:
        blocks = list(FENCES.finditer((ROOT / "docs/02-architecture.md").read_text()))
        for index, name in names:
            full = f"{package.__name__}.{name}"
            module = types.ModuleType(full)
            module.__package__ = package.__name__
            sys.modules[full] = module
            exec(compile(blocks[index][1], name, "exec"), module.__dict__)
        from tachyon_api import Tachyon
        application = Tachyon()
        application.include_router(module.router)
        with TachyonTestClient(application) as client:
            response = client.post("/users/", json={"name": "Ada", "email": "ada@example.com", "password": "hidden"})
            assert response.status_code == 200, response.text
            assert "password" not in response.json()
            assert client.get("/users/").json() == [response.json()]
            assert client.post("/users/", json={"name": "Ada", "email": "ada@example.com", "password": "hidden"}).status_code == 409
    finally:
        for name in list(sys.modules):
            if name.startswith(package.__name__):
                sys.modules.pop(name)


def test_documented_scaffolding_flow(tmp_path, monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "my-api", "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    project = tmp_path / "my_api"
    assert project.is_dir()
    monkeypatch.chdir(project)
    result = runner.invoke(cli, ["g", "service", "user", "--crud"])
    assert result.exit_code == 0, result.output
    with (project / "app.py").open("a") as target:
        target.write("\nfrom modules.user import router as users_router\napp.include_router(users_router)\n")
    script = '''from app import app
from tachyon_api.testing import TachyonTestClient
with TachyonTestClient(app) as client:
    created = client.post('/users/', json={'name': 'Ada'})
    assert created.status_code == 200, created.text
    item = created.json()
    assert client.get('/users/' + item['id']).json() == item
    assert client.get('/users/').status_code == 200
'''
    environment = {**os.environ, "PYTHONPATH": str(ROOT)}
    completed = subprocess.run([sys.executable, "-c", script], cwd=project, env=environment, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_generated_ai_skill_python_blocks_compile():
    from tachyon_api.cli.templates.ai_skill import _full_content

    content = _full_content()
    blocks = list(FENCES.finditer(content))
    assert blocks
    for index, match in enumerate(blocks):
        compile(match[1], f"generated-ai-context:{index}", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


def test_validation_migration_preserves_unknown_field_policy():
    import msgspec

    index = next(index for path, index, source in BLOCKS if path.name == "14-migration-fastapi.md" and "class User(Struct, forbid_unknown_fields=True)" in source)
    module = load_block("docs/14-migration-fastapi.md", index)
    user = msgspec.json.decode(b'{"name":"Ada","email":"ada@example.com"}', type=module.User)
    assert user.name == "Ada"
    with pytest.raises(msgspec.ValidationError, match="unknown field"):
        msgspec.json.decode(b'{"name":"Ada","email":"ada@example.com","admin":true}', type=module.User)


def test_optional_bearer_example_validates_tokens_before_private_access():
    module = load_block("docs/06-security.md", 0)
    source = next(source for path, _, source in BLOCKS if path.name == "06-security.md" and "auto_error=False" in source)
    exec(compile(source, "optional-bearer-example", "exec"), module.__dict__)
    with TachyonTestClient(module.app) as client:
        assert client.get("/items").json() == {"items": ["public"], "user": "anonymous"}
        assert client.get("/items", headers={"Authorization": "Bearer invalid"}).status_code == 401
        assert client.get("/items", headers={"Authorization": "Bearer valid_token"}).json() == {
            "items": ["public", "private"], "user": "John",
        }


def test_validation_guide_error_payload_matches_runtime():
    import json

    path = ROOT / "docs/05-validation.md"
    index = next(index for document, index, source in BLOCKS if document == path and "class CreateUser" in source)
    module = load_block("docs/05-validation.md", index)
    examples = [json.loads(match[1]) for match in re.finditer(r"^```json\n(.*?)^```", path.read_text(), re.MULTILINE | re.DOTALL)]
    with TachyonTestClient(module.app) as client:
        assert client.post("/users", json=examples[0]).status_code == 200
        response = client.post("/users", json=examples[1])
        assert response.status_code == 422
        assert response.json() == examples[2]


def test_best_practices_exception_handler_uses_domain_exception_fields():
    from tachyon_api import HTTPException, Tachyon
    from starlette.responses import JSONResponse

    namespace = {"HTTPException": HTTPException, "JSONResponse": JSONResponse, "app": Tachyon()}
    sources = [source for path, _, source in BLOCKS if path.name == "15-best-practices.md"]
    for marker in ["class ConflictError", "def handle_conflict"]:
        source = next(source for source in sources if marker in source)
        exec(compile(source, "best-practices-errors", "exec"), namespace)

    @namespace["app"].get("/conflict")
    def conflict():
        raise namespace["ConflictError"]("Already exists")

    with TachyonTestClient(namespace["app"]) as client:
        response = client.get("/conflict")
        assert response.status_code == 409
        assert response.json() == {"detail": "Already exists"}
