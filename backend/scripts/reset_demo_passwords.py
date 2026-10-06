"""
Sets a known, fixed password (from scripts/migrations/creds.json) on each of the
standard demo accounts — regardless of whether they already existed — and
ensures the supporting profile records (Employee / PartnerAccount / Client)
each portal needs are present.

Unlike the seeder (app/seeders/seed.py), which only sets a password for
accounts it *creates* on that run, this script forces every demo account to a
known password. Typical use: after running the CoreFusion-owned auth migration
(alembic revision 370721f881ed), which backfills pre-existing users with an
unusable placeholder hash, so every demo account now requires forgot-password
for no other reason than it predates the migration.

Reads the full roster from scripts/migrations/creds.json (gitignored, local
file — edit it to change a demo password). Also resets any account lockout
state and marks pre-existing demo users email-verified so login works
immediately. Writes (overwrites) CREDENTIALS.local.md in this folder.

Refuses to run when ENV=production. Usage (from backend/, venv active):

    python scripts/reset_demo_passwords.py
"""
import asyncio
import os
from datetime import UTC, datetime

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.password import hash_password  # noqa: E402
from app.models.client import Client  # noqa: E402
from app.models.employee import Employee  # noqa: E402
from app.models.enums import PartnerType  # noqa: E402
from app.models.partner_account import PartnerAccount  # noqa: E402
from app.models.user import User  # noqa: E402
from app.seeders import seed  # noqa: E402

ROLE_LABEL_OVERRIDES = {"hr": "HR", "qa": "QA"}


def write_credentials_md() -> None:
    """Overwrite CREDENTIALS.local.md with every demo account's current password."""
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CREDENTIALS.local.md")
    rows = []
    for role_key, account in seed.CREDS.items():
        role_label = ROLE_LABEL_OVERRIDES.get(role_key) or role_key.replace("_", " ").title()
        rows.append((role_label, account.get("department", "—"), account["email"], account["password"]))

    lines = [
        "# CoreFusion Demo Credentials",
        "",
        "**Generated locally by `scripts/reset_demo_passwords.py` — never commit this file.**",
        f"Generated at: {datetime.now(UTC).isoformat()}",
        "",
        "Fixed, known passwords read from `scripts/migrations/creds.json` (gitignored,",
        f"local-only — edit that file to change a demo password). {len(rows)} account(s).",
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

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(rows)} account(s) to {out_path} (gitignored, local-only).")


async def _upsert_demo_users(db) -> None:
    for role_key in seed.ROLE_KEYS:
        account = seed.CREDS[role_key]
        user = (
            await db.execute(select(User).where(User.email == account["email"]))
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if user:
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(
                    password_hash=hash_password(account["password"]),
                    role=role_key,
                    name=account["name"],
                    is_active=True,
                    is_email_verified=True,
                    email_verified_at=now,
                    failed_login_attempts=0,
                    is_locked=False,
                    locked_until=None,
                )
            )
            print(f"updated {account['email']} (role={role_key}, password reset)")
        else:
            db.add(User(
                password_hash=hash_password(account["password"]),
                name=account["name"],
                email=account["email"],
                phone=account.get("phone"),
                role=role_key,
                is_active=True,
                is_email_verified=True,
                email_verified_at=now,
            ))
            print(f"created {account['email']} (role={role_key})")


async def _ensure_supporting_profiles(db) -> None:
    # Must run after the user upserts are flushed so lookups see the users.
    await db.flush()

    dept_ids = {}
    for name in seed.DEPARTMENTS:
        exists = (await db.execute(select(seed.Department).where(seed.Department.name == name))).scalar_one_or_none()
        if not exists:
            dept = seed.Department(name=name)
            db.add(dept)
            await db.flush()
            dept_ids[name] = dept.id
        else:
            dept_ids[name] = exists.id

    for role_key in seed.ROLE_KEYS:
        account = seed.CREDS[role_key]
        user = (
            await db.execute(select(User).where(User.email == account["email"]))
        ).scalar_one_or_none()
        if not user:
            continue

        if "employee_code" in account:
            emp = (
                await db.execute(select(Employee).where(Employee.user_id == user.id))
            ).scalar_one_or_none()
            if not emp:
                db.add(Employee(
                    user_id=user.id,
                    employee_code=account["employee_code"],
                    department_id=dept_ids.get(account.get("department")),
                    designation=account.get("designation"),
                    status="active",
                    employment_type="full_time",
                ))
                print(f"  Employee record created for {account['email']}")

        if role_key == "partner" and user.role == "partner":
            partner = (
                await db.execute(select(PartnerAccount).where(PartnerAccount.user_id == user.id))
            ).scalar_one_or_none()
            if not partner:
                acct_mgr = (
                    await db.execute(select(Employee).join(User).where(User.email == seed.SALES_EMAIL))
                ).scalar_one_or_none()
                db.add(PartnerAccount(
                    user_id=user.id,
                    company_name=account.get("company_name"),
                    partnership_type=PartnerType(account.get("partnership_type", "reseller")),
                    industry=account.get("industry"),
                    country=account.get("country"),
                    website=account.get("website"),
                    account_manager_id=acct_mgr.id if acct_mgr else None,
                ))
                print(f"  Partner account profile created for {account['email']}")

        if role_key == "client" and user.role == "client":
            client = (
                await db.execute(select(Client).where(Client.user_id == user.id))
            ).scalar_one_or_none()
            if not client:
                acct_mgr = (
                    await db.execute(select(Employee).join(User).where(User.email == seed.SALES_EMAIL))
                ).scalar_one_or_none()
                db.add(Client(
                    user_id=user.id,
                    company_name=account.get("company_name"),
                    industry=account.get("industry"),
                    country=account.get("country"),
                    website=account.get("website"),
                    billing_address=account.get("billing_address"),
                    account_manager_id=acct_mgr.id if acct_mgr else None,
                ))
                print(f"  Client profile created for {account['email']}")


async def main() -> None:
    if seed.settings.env.lower() in {"production", "prod"}:
        raise SystemExit(
            "Refusing to run against ENV=production. This resets demo-account passwords "
            "for local/dev/staging only."
        )

    async with AsyncSessionLocal() as db:
        await _upsert_demo_users(db)
        await _ensure_supporting_profiles(db)
        await db.commit()
        print(f"\n{len(seed.CREDS)} demo account(s) now use the passwords in creds.json.")

    write_credentials_md()


if __name__ == "__main__":
    asyncio.run(main())