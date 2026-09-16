# Backend service (FastAPI)

FastAPI + SQLAlchemy + Alembic. See repo root `README.md` for the canonical test command.

## Local commands (inside the `backend` container)

```
alembic upgrade head          # apply migrations
alembic revision --autogenerate -m "message"   # generate a migration from model changes
pytest -q                     # run tests
```
