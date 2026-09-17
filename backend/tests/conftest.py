import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers all models on Base.metadata
from app.db.session import Base, engine


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
