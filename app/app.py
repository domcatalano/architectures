import os
from typing import Literal
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from loguru import logger
from pydantic import BaseModel

from . driver import RayEntryPoint, get_anyscale_address


class ServiceStatus(BaseModel):
    status: Literal["OK", "Unhealthy"]

    class Config:
        extra = "forbid"


app = FastAPI(
    title="Anyscale Demo Architecture",
    description="Provides model training and prediction services",
    version=os.environ.get("IMAGE_TAG", "development"),
)


global entry_point

@app.on_event("startup")
def on_startup(stage=None):
    global entry_point

    entry_point = RayEntryPoint(get_anyscale_address(stage))

@app.on_event("shutdown")
async def on_shutdown():
    entry_point.cleanup()

# first iteration - synchronous ray task
@app.post(
    "/service/ray_submit",
    response_model_exclude_unset=True,
    summary="Ray Job",
    tags=["Ray"],
)
async def start_ray_job():
    entry_point.execute()
    return {"status":"Job submitted"}

@app.get(
    "/service/ray_result",
    summary="Ray Result",
    tags=["Ray"],
)
async def get_job_result():
    result = entry_point.respond()
    return {"status":str(result)}

@app.get(
    "/service/status",
    response_model=ServiceStatus,
    response_model_exclude_unset=True,
    tags=["Service"],
)
async def status():
    return {"status": "OK"}



##-------------------------main------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
