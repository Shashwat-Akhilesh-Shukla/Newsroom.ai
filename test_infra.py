import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from redis import asyncio as aioredis

load_dotenv()

async def test_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL missing")
        return False
    try:
        # Convert to asyncpg if needed
        if "postgresql+asyncpg" not in db_url and "postgresql://" in db_url:
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        
        print(f"Testing DB connection to: {db_url}")
        engine = create_async_engine(db_url)
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

async def test_redis():
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        print("❌ REDIS_URL missing")
        return False
    try:
        print(f"Testing Redis connection to: {redis_url}")
        redis = aioredis.from_url(redis_url)
        await redis.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

async def main():
    db_ok = await test_db()
    redis_ok = await test_redis()
    if db_ok and redis_ok:
        print("\n🎉 All infra checks passed!")
    else:
        print("\n⚠️ Some infra checks failed.")

if __name__ == "__main__":
    asyncio.run(main())
