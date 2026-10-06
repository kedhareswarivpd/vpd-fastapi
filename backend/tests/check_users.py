import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def check_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT id, email, name, role FROM users ORDER BY created_at DESC LIMIT 10"))
        users = result.fetchall()
        
        print("\n" + "="*60)
        print("USERS IN DATABASE")
        print("="*60)
        
        if not users:
            print("\n[NO USERS] No users found in database!")
        else:
            print(f"\n[OK] Found {len(users)} users:")
            print()
            for user in users:
                print(f"  ID: {user[0]}")
                print(f"  Email: {user[1]}")
                print(f"  Name: {user[2]}")
                print(f"  Role: {user[3]}")
                print()
        
        print("="*60)

asyncio.run(check_users())
