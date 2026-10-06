import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def q():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text(
            "SELECT id, email, name, role FROM users WHERE email ILIKE '%corefusion%' OR email ILIKE '%employee%' OR email ILIKE '%hr%' OR email ILIKE '%developer%' ORDER BY created_at DESC"
        ))
        rows = r.fetchall()
        if not rows:
            print("No matching users found.")
        for row in rows:
            print(f"ID: {row[0]}  Email: {row[1]}  Name: {row[2]}  Role: {row[3]}")

asyncio.run(q())
