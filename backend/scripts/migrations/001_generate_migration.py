"""
Run this script when you have access to the target PostgreSQL database:

    cd backend
    python scripts/generate_migration.py

It will run `alembic revision --autogenerate` against whatever database
is configured in your backend/.env file.

Requires a running PostgreSQL with the schema already existing (even if empty)
so that Alembic can do its CREATE TABLE diff.
"""
import os
import subprocess
import sys

if __name__ == "__main__":
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "initial"],
        cwd=backend_dir,
    )
    sys.exit(result.returncode)
