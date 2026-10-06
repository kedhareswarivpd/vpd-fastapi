"""
Seed demo users, departments, and reference content, then write a
human-readable credentials sheet to scripts/migrations/CREDENTIALS.local.md.

This is a thin wrapper around the actual seeding logic in
app/seeders/seed.py (single source of truth for what gets created —
this script does not duplicate it). Login IDs, passwords, and account
details all come from scripts/migrations/creds.json (gitignored,
local-only — see that file to add/change a demo account).

Usage (from the backend/ directory, with the venv active and the
database reachable — e.g. `docker compose up -d postgres` first):

    python scripts/migrations/002_seed_users.py

Safe to re-run: existing accounts/departments are left untouched. The
credentials sheet always lists the full roster from creds.json (not just
accounts created this run) — passwords are fixed/deterministic, not
randomly generated, so there's nothing to lose by always regenerating it.
"""
import asyncio
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.seeders import seed  # noqa: E402

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CREDENTIALS.local.md")


def write_credentials_md(newly_created: dict[str, str]) -> None:
    ROLE_LABEL_OVERRIDES = {"hr": "HR", "qa": "QA"}

    rows = []
    for role_key, account in seed.CREDS.items():
        role_label = ROLE_LABEL_OVERRIDES.get(role_key) or role_key.replace("_", " ").title()
        rows.append((role_label, account.get("department", "—"), account["email"], account["password"]))

    lines = [
        "# CoreFusion Demo Credentials",
        "",
        "**Generated locally by `scripts/migrations/002_seed_users.py` — never commit this file.**",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "Fixed, known passwords read from `scripts/migrations/creds.json` (gitignored,",
        "local-only — edit that file to change a demo password). Lists the full account",
        f"roster every run, not just accounts created this run ({len(newly_created)} new this run).",
        "",
        "| Role | Department | Email | Password |",
        "|------|------------|-------|----------|",
    ]
    for role_label, dept, email, password in rows:
        lines.append(f"| {role_label} | {dept} | {email} | `{password}` |")

    lines += [
        "",
        "## Departments seeded",
        "",
        *[f"- {d}" for d in seed.DEPARTMENTS],
        "",
    ]

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(rows)} account(s) to {OUT_PATH} (gitignored, local-only).")


async def main():
    await seed.run()
    write_credentials_md(seed._generated_credentials)


if __name__ == "__main__":
    asyncio.run(main())
