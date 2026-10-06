import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reports_migration_helper_detects_existing_tables():
    module = load_module(
        "reports_migration",
        Path(__file__).resolve().parent.parent / "alembic" / "versions" / "b2c3d4e5f6a7_add_reports_table.py",
    )
    engine = create_engine("sqlite:///:memory:")

    assert module.table_exists(engine, "reports") is False

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE reports (id INTEGER)"))

    assert module.table_exists(engine, "reports") is True
