import asyncio
import asyncpg
from app.config import settings


async def init_db():
    database_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    conn = await asyncpg.connect(database_url)
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()

    print("Executing schema.sql...")
    try:
        await conn.execute(schema_sql)
        print("Schema executed successfully!")
    except Exception as e:
        print(f"Error during schema execution: {e}")
        if "vector" in str(e).lower():
            print("Note: Ensure pgvector extension is installed in PostgreSQL.")

    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"
    )
    tables = [r["table_name"] for r in rows]
    print(f"Tables now in db_ai_drive: {tables}")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(init_db())
