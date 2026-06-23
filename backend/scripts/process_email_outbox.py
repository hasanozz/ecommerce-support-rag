import asyncio

from backend.app.database import SessionLocal, close_database
from backend.app.services.email import EmailService


async def main() -> None:
    async with SessionLocal() as session:
        count = await EmailService().send_pending(session)
    await close_database()
    print(f"EMAIL_OUTBOX_PROCESSED sent={count}")


if __name__ == "__main__":
    asyncio.run(main())
