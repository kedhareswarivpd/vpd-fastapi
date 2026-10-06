"""
Run this once to fix a user's role in the database.
Usage:
    python fix_user_role.py employee@corefusion.com hr
"""
import asyncio
import sys

from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.user import User


async def fix_role(email: str, new_role: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(User).where(User.email == email).values(role=new_role).returning(User.id, User.email, User.role)
        )
        row = result.fetchone()
        await db.commit()
        if row:
            print(f"✅ Updated: {row[1]}  role → {row[2]}")
        else:
            print(f"❌ No user found with email: {email}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fix_user_role.py <email> <role>")
        print("Roles: employee, developer, sales, marketing, project_manager, qa, support, finance, hr, admin, super_admin, client")
        sys.exit(1)
    asyncio.run(fix_role(sys.argv[1], sys.argv[2]))
