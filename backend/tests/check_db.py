import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def check_db():
    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text('SELECT 1'))
            print('[OK] Database connection successful')
        
        # New connection for second query
        async with engine.connect() as conn:
            # Check for any tables
            result = await conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            ))
            rows = result.fetchall()  # Remove await - fetchall is not async
            tables = list(rows)
            print(f'[INFO] Tables in database: {len(tables)}')
            if tables:
                for table in tables:
                    print(f'  - {table[0]}')
            else:
                print('[INFO] Database is empty - no tables found')
                
    except Exception as e:
        print(f'[ERROR] Database check failed: {str(e)[:100]}')
    finally:
        await engine.dispose()

asyncio.run(check_db())
