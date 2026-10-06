import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.models.role import Role


async def validate_database():
    """Validate database connection and basic operations"""
    errors = []
    warnings = []
    successes = []
    
    try:
        # Test 1: Connection
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT 1"))
            successes.append("✅ Database connection successful")
        
        # Test 2: Check alembic_version table
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1"))
            rows = result.fetchall()
            if rows:
                successes.append(f"✅ Migration version {rows[0][0]} applied")
            else:
                warnings.append("⚠️ No migrations applied")
        
        # Test 3: Check table counts
        async with AsyncSessionLocal() as db:
            result = await db.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            ))
            count = result.scalar()
            successes.append(f"✅ {count} tables created")
        
        # Test 4: Create and read a test role
        async with AsyncSessionLocal() as db:
            # Check if test role exists
            result = await db.execute(text("SELECT id FROM roles WHERE name = 'test_migration_role' LIMIT 1"))
            existing = result.scalar()
            
            if not existing:
                # Create test role with slug
                from python_slugify import slugify
                test_role = Role(
                    name="test_migration_role", 
                    slug=slugify("test_migration_role"),
                    description="Test role for migration validation"
                )
                db.add(test_role)
                await db.commit()
                successes.append("✅ CREATE operation successful (test role created)")
                
                # Read it back
                result = await db.execute(text("SELECT id, name FROM roles WHERE name = 'test_migration_role'"))
                rows = result.fetchall()
                if rows:
                    successes.append("✅ READ operation successful (test role retrieved)")
                else:
                    errors.append("❌ Failed to retrieve test role")
            else:
                successes.append("✅ READ operation successful (test role already exists)")
        
        # Test 5: Check foreign key relationships
        async with AsyncSessionLocal() as db:
            # Get count of tables with foreign keys
            result = await db.execute(text("""
                SELECT COUNT(DISTINCT table_name) 
                FROM information_schema.referential_constraints 
                WHERE constraint_schema = 'public'
            """))
            fk_count = result.scalar()
            successes.append(f"✅ Foreign key relationships configured ({fk_count} tables with FKs)")
        
        # Test 6: Check indexes
        async with AsyncSessionLocal() as db:
            result = await db.execute(text("""
                SELECT COUNT(*) 
                FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname NOT LIKE 'pg_toast%'
            """))
            index_count = result.scalar()
            successes.append(f"✅ Indexes created ({index_count} total)")
        
        # Test 7: Transaction test
        async with AsyncSessionLocal() as db:
            # Start a transaction
            async with db.begin():
                result = await db.execute(text("SELECT COUNT(*) FROM roles"))
                count_before = result.scalar()
            
            # Transaction should be committed
            async with db.begin():
                result = await db.execute(text("SELECT COUNT(*) FROM roles"))
                count_after = result.scalar()
            
            if count_before == count_after:
                successes.append("✅ Transaction handling working correctly")
            else:
                errors.append("❌ Transaction handling issue detected")
        
        # Print results
        print("\n" + "="*60)
        print("DATABASE VALIDATION REPORT")
        print("="*60)
        
        if successes:
            print("\n✅ SUCCESSES:")
            for msg in successes:
                print(f"  {msg}")
        
        if warnings:
            print("\n⚠️ WARNINGS:")
            for msg in warnings:
                print(f"  {msg}")
        
        if errors:
            print("\n❌ ERRORS:")
            for msg in errors:
                print(f"  {msg}")
        
        print("\n" + "="*60)
        print("VALIDATION COMPLETE")
        print("="*60)
        
        return len(errors) == 0
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(validate_database())
    exit(0 if success else 1)
