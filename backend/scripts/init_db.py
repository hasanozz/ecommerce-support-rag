import asyncio

from backend.app.database import close_database, initialize_database


async def main() -> None:
    await initialize_database()
    await close_database()
    print("DATABASE_INITIALIZED")


if __name__ == "__main__":
    asyncio.run(main())
