"""
Update admin/superadmin credentials in the database.

- Changes existing admin@corefusiontech.com (currently super_admin) to role=admin
  and updates its password (local Argon2id hash — CoreFusion owns auth end to
  end, there's no external identity provider to also update).
- Creates superadmin@corefusiontech.com with role=super_admin if it doesn't already exist.

Passwords are read from the ADMIN_PASSWORD/SUPER_ADMIN_PASSWORD env vars or
prompted interactively. Standalone maintenance script — not part of the
automated pytest suite (no test_ functions), run directly with
`python tests/update_credentials.py`.
"""
import asyncio
import os
import uuid
from getpass import getpass

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.password import hash_password
from app.models.user import User

SUPER_ADMIN_EMAIL = "superadmin@corefusiontech.com"
ADMIN_EMAIL = "admin@corefusiontech.com"

SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD") or getpass(f"Password for {SUPER_ADMIN_EMAIL}: ")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or getpass(f"Password for {ADMIN_EMAIL}: ")


async def main():
    async with AsyncSessionLocal() as db:
        # 1. Update existing admin@corefusiontech.com -> role=admin + new password
        existing_admin = (await db.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one_or_none()
        if existing_admin:
            await db.execute(
                update(User).where(User.id == existing_admin.id).values(
                    role="admin", name="CoreFusion Admin", password_hash=hash_password(ADMIN_PASSWORD),
                )
            )
            await db.commit()
            print(f"[OK] Updated {ADMIN_EMAIL}: role -> admin, name -> CoreFusion Admin, password updated")
        else:
            print(f"[INFO] {ADMIN_EMAIL} not found in local DB — will be created by seed script")

        # 2. Create superadmin@corefusiontech.com if it doesn't exist
        existing_super = (await db.execute(select(User).where(User.email == SUPER_ADMIN_EMAIL))).scalar_one_or_none()
        if existing_super:
            print(f"[OK] {SUPER_ADMIN_EMAIL} already exists")
        else:
            super_admin = User(
                id=uuid.uuid4(),
                name="CoreFusion Super Admin",
                email=SUPER_ADMIN_EMAIL,
                password_hash=hash_password(SUPER_ADMIN_PASSWORD),
                role="super_admin",
                is_active=True,
                is_email_verified=True,
            )
            db.add(super_admin)
            await db.commit()
            print(f"[OK] Created {SUPER_ADMIN_EMAIL} with role=super_admin")

        # 3. Verify final state
        print("\n=== Final user state ===")
        for email in (ADMIN_EMAIL, SUPER_ADMIN_EMAIL):
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user:
                print(f"  {user.email}  role={user.role}  name={user.name}")
            else:
                print(f"  {email}  NOT FOUND")


if __name__ == "__main__":
    asyncio.run(main())
