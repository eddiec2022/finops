from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.cost import router as cost_router
from app.api.forecast import router as forecast_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.recommendations import router as recommendations_router
from app.api.utilization import router as utilization_router
from app.core.config import settings

app = FastAPI(title="FinOps Platform API")

# Task 13 is the first thing that actually calls this API from a browser
# (Task 1's page only ever checked /health, and every other task's "live
# check" was a server-side curl, which isn't subject to the browser's CORS
# policy at all) - so this was never needed until now. Scoped to the known
# dev frontend origin rather than a wildcard, since credentials aren't
# involved here and there's exactly one legitimate caller in this phase.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(utilization_router)
app.include_router(cost_router)
app.include_router(forecast_router)
app.include_router(recommendations_router)
