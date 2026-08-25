"""Test configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from backend.db.session import Base, get_session_dependency
from backend.db.models import Merchant, Customer, Order, PaymentAttempt
from backend.api.main import app


# Use test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/reclaim_test",
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with test_session_maker() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Create test client with overridden database dependency."""
    from httpx import ASGITransport, AsyncClient
    
    async def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session_dependency] = override_get_session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_merchant(db_session: AsyncSession) -> Merchant:
    merchant = Merchant(
        merchant_id="merchant_test",
        max_retries=3,
        contact_budget_per_day=2,
    )
    db_session.add(merchant)
    await db_session.commit()
    await db_session.refresh(merchant)
    return merchant


@pytest_asyncio.fixture
async def sample_customer(db_session: AsyncSession) -> Customer:
    customer = Customer(
        customer_id="cust_test",
        recovery_propensity=0.5,
        customer_value=10000,
    )
    db_session.add(customer)
    await db_session.commit()
    await db_session.refresh(customer)
    return customer


@pytest_asyncio.fixture
async def sample_order(
    db_session: AsyncSession,
    sample_merchant: Merchant,
    sample_customer: Customer,
) -> Order:
    order = Order(
        order_id="order_test",
        merchant_id=sample_merchant.merchant_id,
        customer_id=sample_customer.customer_id,
        amount=5000,
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest_asyncio.fixture
async def sample_attempt(
    db_session: AsyncSession,
    sample_order: Order,
) -> PaymentAttempt:
    attempt = PaymentAttempt(
        payment_id="pay_test_1",
        order_id=sample_order.order_id,
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="issuer_timeout",
    )
    db_session.add(attempt)
    await db_session.commit()
    await db_session.refresh(attempt)
    return attempt