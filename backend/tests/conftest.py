import pytest
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - registers all models on Base.metadata
from app.db.session import Base, engine


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
