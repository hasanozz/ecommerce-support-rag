from __future__ import annotations

import asyncio

from backend.app.database import SessionLocal
from backend.app.services.demo_seed import DemoSeedService


async def main() -> None:
    async with SessionLocal() as session:
        summary = await DemoSeedService().seed_catalog(session)
        await session.commit()
    print(
        "DEMO_SEED_OK "
        f"products={summary['products']} "
        f"coupons={summary['coupons']} "
        f"reviews={summary['reviews']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
