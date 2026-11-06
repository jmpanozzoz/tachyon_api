"""Reference/session starter patterns share a checked source contract."""
from pathlib import Path
from tachyon_api.cli.templates import persistence


def test_postgres_database_template_matches_reference():
    root = Path(__file__).resolve().parents[1]
    assert persistence.DATABASE == (root / "example/shared/database.py").read_text()
