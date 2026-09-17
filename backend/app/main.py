from fastapi import FastAPI

from app.api.cost import router as cost_router
from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.utilization import router as utilization_router

app = FastAPI(title="FinOps Platform API")

app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(utilization_router)
app.include_router(cost_router)
