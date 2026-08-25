"""Database initialization script."""

import asyncio
import sys

from backend.db.session import init_db


async def main() -> None:
    print("Initializing database...")
    await init_db()
    print("Database initialized successfully!")


if __name__ == "__main__":
    asyncio.run(main())