import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers all models on Base.metadata
from app.db.session import Base, engine, get_db
from app.main import app


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    # join_transaction_mode="create_savepoint" makes session.commit() (called by
    # sync_inventory/sync_utilization) release a SAVEPOINT instead of the outer
    # transaction, so the rollback below actually undoes everything the test wrote
    # instead of leaking rows into the real dev database.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the same transaction-scoped session as db_session.

    Without this override, a request would go through get_db's own
    SessionLocal() on a separate connection, which can't see anything seeded via
    db_session (it's sat in an uncommitted transaction on a different
    connection).
    """

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
