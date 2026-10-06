import asyncio
import json
import os
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.password import hash_password
from app.models.analytics import PageView
from app.models.client import Client
from app.models.department import Department
from app.models.employee import Employee
from app.models.enums import PartnerType
from app.models.partner_account import PartnerAccount
from app.models.setting import Setting
from app.models.user import User

# Demo account emails/passwords/profile fields are NOT generated here — they are
# read from scripts/migrations/creds.json, a gitignored, local-only file that is
# the single source of truth for every seeded login. Edit that file to change a
# demo password; this module just seeds whatever it contains. See CF-AUD-007.
_CREDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "scripts", "migrations", "creds.json",
)
_generated_credentials: dict[str, str] = {}


def _load_creds() -> dict:
    if not os.path.exists(_CREDS_PATH):
        raise SystemExit(
            f"creds.json not found at {_CREDS_PATH}. This file holds the fixed demo "
            "login/password/account details seeded locally — create it (see backend/"
            "scripts/migrations/creds.json.example if present, or copy the structure "
            "documented in scripts/README.md) before running the seeder."
        )
    with open(_CREDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


CREDS = _load_creds()

DEPARTMENTS = [
    "Engineering", "Design", "Sales", "Marketing", "Human Resources",
    "Finance", "Quality Assurance", "DevOps", "Customer Support", "Management",
]

# Role -> UserRole enum value. Kept explicit (rather than using the creds.json
# key directly) so a typo'd JSON key fails loudly instead of silently seeding
# a bogus role.
ROLE_KEYS = [
    "super_admin", "admin", "employee", "sales", "hr", "marketing",
    "project_manager", "developer", "qa", "support", "finance", "partner", "client",
]

# Back-compat module-level constants (EMAIL_DEPARTMENT lookups, credential-sheet
# role-name derivation, etc. all key off these) — now sourced from creds.json.
SUPER_ADMIN_EMAIL = CREDS["super_admin"]["email"]
ADMIN_EMAIL = CREDS["admin"]["email"]
EMPLOYEE_EMAIL = CREDS["employee"]["email"]
SALES_EMAIL = CREDS["sales"]["email"]
HR_EMAIL = CREDS["hr"]["email"]
MARKETING_EMAIL = CREDS["marketing"]["email"]
PM_EMAIL = CREDS["project_manager"]["email"]
DEVELOPER_EMAIL = CREDS["developer"]["email"]
QA_EMAIL = CREDS["qa"]["email"]
SUPPORT_EMAIL = CREDS["support"]["email"]
FINANCE_EMAIL = CREDS["finance"]["email"]
PARTNER_EMAIL = CREDS["partner"]["email"]
CLIENT_EMAIL = CREDS["client"]["email"]


async def _seed_role_user(db, role_key: str, user_role: str):
    account = CREDS[role_key]
    existing = (await db.execute(select(User).where(User.email == account["email"]))).scalar_one_or_none()
    if existing:
        print(f"i  {user_role} user already exists")
        return

    user = User(
        id=uuid.uuid4(),
        password_hash=hash_password(account["password"]),
        name=account["name"],
        email=account["email"],
        role=user_role,
        phone=account.get("phone"),
        is_active=True,
        is_email_verified=True,
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    _generated_credentials[account["email"]] = account["password"]
    print(f"{user_role} user created: {account['email']}")


async def run():
    if settings.env.lower() in {"production", "prod"}:
        raise SystemExit(
            "Refusing to run the demo seed script against ENV=production. "
            "This creates known-role demo accounts and is for local/dev/staging only."
        )

    async with AsyncSessionLocal() as db:
        for role_key in ROLE_KEYS:
            await _seed_role_user(db, role_key, role_key)
        # Flush so newly created users are visible to the `select()` lookups
        # below regardless of whether the departments loop happens to flush
        # too (it only does when a department doesn't already exist).
        await db.flush()

        dept_map = {}
        for name in DEPARTMENTS:
            exists = (await db.execute(select(Department).where(Department.name == name))).scalar_one_or_none()
            if not exists:
                dept = Department(name=name)
                db.add(dept)
                await db.flush()
                dept_map[name] = dept.id
            else:
                dept_map[name] = exists.id
        print("Departments seeded")

        # Seed Employee records for every role that carries an employee_code in
        # creds.json, so self-service endpoints (attendance, payslips, etc.) work.
        for role_key in ROLE_KEYS:
            account = CREDS[role_key]
            if "employee_code" not in account:
                continue
            user = (await db.execute(select(User).where(User.email == account["email"]))).scalar_one_or_none()
            if not user:
                continue
            existing_emp = (await db.execute(select(Employee).where(Employee.user_id == user.id))).scalar_one_or_none()
            if existing_emp:
                print(f"  Employee record already exists for {account['email']}")
                continue
            emp = Employee(
                user_id=user.id,
                employee_code=account["employee_code"],
                department_id=dept_map.get(account.get("department")),
                designation=account.get("designation"),
                status="active",
                employment_type="full_time",
            )
            db.add(emp)
            print(f"  Employee record created for {account['email']}")

        # Seed a partner_accounts profile for the demo Partner Portal login,
        # account-managed by the Sales employee for a realistic relationship.
        partner_account_cfg = CREDS["partner"]
        partner_user = (await db.execute(select(User).where(User.email == partner_account_cfg["email"]))).scalar_one_or_none()
        if partner_user:
            existing_partner_account = (
                await db.execute(select(PartnerAccount).where(PartnerAccount.user_id == partner_user.id))
            ).scalar_one_or_none()
            if not existing_partner_account:
                sales_user = (await db.execute(select(User).where(User.email == SALES_EMAIL))).scalar_one_or_none()
                account_manager = None
                if sales_user:
                    account_manager = (
                        await db.execute(select(Employee).where(Employee.user_id == sales_user.id))
                    ).scalar_one_or_none()
                db.add(PartnerAccount(
                    user_id=partner_user.id,
                    company_name=partner_account_cfg.get("company_name"),
                    partnership_type=PartnerType(partner_account_cfg.get("partnership_type", "reseller")),
                    industry=partner_account_cfg.get("industry"),
                    country=partner_account_cfg.get("country"),
                    website=partner_account_cfg.get("website"),
                    account_manager_id=account_manager.id if account_manager else None,
                ))
                print(f"  Partner account profile created for {partner_account_cfg['email']}")
            else:
                print(f"  Partner account profile already exists for {partner_account_cfg['email']}")

        # Seed a clients profile for the demo Client Portal login, account-managed
        # by the Sales employee for a realistic relationship.
        client_account_cfg = CREDS["client"]
        client_user = (await db.execute(select(User).where(User.email == client_account_cfg["email"]))).scalar_one_or_none()
        if client_user:
            existing_client = (
                await db.execute(select(Client).where(Client.user_id == client_user.id))
            ).scalar_one_or_none()
            if not existing_client:
                sales_user = (await db.execute(select(User).where(User.email == SALES_EMAIL))).scalar_one_or_none()
                account_manager = None
                if sales_user:
                    account_manager = (
                        await db.execute(select(Employee).where(Employee.user_id == sales_user.id))
                    ).scalar_one_or_none()
                db.add(Client(
                    user_id=client_user.id,
                    company_name=client_account_cfg.get("company_name"),
                    industry=client_account_cfg.get("industry"),
                    country=client_account_cfg.get("country"),
                    website=client_account_cfg.get("website"),
                    billing_address=client_account_cfg.get("billing_address"),
                    account_manager_id=account_manager.id if account_manager else None,
                ))
                print(f"  Client profile created for {client_account_cfg['email']}")
            else:
                print(f"  Client profile already exists for {client_account_cfg['email']}")

        settings_data = [
            ("site.title", "CoreFusion Technologies", "public"),
            ("site.tagline", "Transforming Businesses Through Intelligent Digital Solutions", "public"),
            ("contact.email", "info@corefusiontech.com", "public"),
            ("contact.phone", "+91-11-0000-0000", "public"),
            ("social.linkedin", "https://linkedin.com/company/corefusiontech", "public"),
        ]
        for key, value, group in settings_data:
            exists = (await db.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
            if not exists:
                db.add(Setting(key=key, value=value, group=group))
        print("Default settings seeded")

        existing_views = (await db.execute(select(PageView.id).limit(1))).scalar_one_or_none()
        if not existing_views:
            paths = [
                "/", "/services", "/about", "/portfolio", "/contact",
                "/careers", "/blog", "/solutions", "/products",
                "/technologies", "/industries", "/case-studies",
                "/downloads", "/resources", "/events", "/gallery",
                "/awards", "/faq", "/privacy", "/terms",
                "/login", "/admin", "/client",
            ]
            agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/17.4",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) Mobile/15E148",
                "Mozilla/5.0 (Linux; Android 14) Chrome/125.0 Mobile",
            ]
            now = datetime.utcnow()
            views = []
            for _ in range(200):
                days_ago = random.randint(0, 30)
                hours_ago = random.randint(0, 23)
                views.append(PageView(
                    path=random.choice(paths),
                    ip_address=f"{random.randint(10,220)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
                    user_agent=random.choice(agents),
                    viewed_at=now - timedelta(days=days_ago, hours=hours_ago),
                ))
            db.add_all(views)
            print(f"Seeded {len(views)} page views")

        await db.commit()

        if _generated_credentials:
            print(f"\n{len(_generated_credentials)} new demo account(s) created this run (passwords per creds.json).")

        print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(run())
