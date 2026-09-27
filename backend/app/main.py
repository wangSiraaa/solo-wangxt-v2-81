"""FastAPI 入口。

启动后：
  - API 文档: http://localhost:8000/docs
  - 本服务为教学模拟，不连接真实闸门，不替代现实供水决策。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routers.api import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="水库教学模拟 API",
    version="1.0.0",
    description="固定时间步水量平衡教学系统：入流、蒸发、放水、弃水与库容变化逐时段演算。",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
