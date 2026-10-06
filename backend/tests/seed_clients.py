"""
Create Client profile records for all users with role=client that don't have one yet.
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.client import Client
from app.models.user import User


async def main():
    async with AsyncSessionLocal() as db:
        # Find all client-role users
        result = await db.execute(select(User).where(User.role == "client"))
        users = result.scalars().all()
        print(f"Found {len(users)} client-role users")

        created = 0
        for user in users:
            existing = (await db.execute(select(Client).where(Client.user_id == user.id))).scalar_one_or_none()
            if existing:
                continue
            company_name = user.name or user.email.split("@")[0]
            client = Client(
                user_id=user.id,
                company_name=company_name,
                industry=None,
                country=None,
            )
            db.add(client)
            created += 1
            print(f"  Created client profile for {user.email}")

        await db.commit()
        print(f"\nCreated {created} client profiles")

        # Verify
        count = (await db.execute(select(Client))).scalars().all()
        print(f"Total client records now: {len(count)}")


if __name__ == "__main__":
    asyncio.run(main())