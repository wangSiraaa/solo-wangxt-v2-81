"""FastAPI 入口。

教学模拟系统：不连接任何真实闸门/现地设备，所有结果仅供课堂使用，
不构成现实供水决策依据。
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import scenarios, simulate

app = FastAPI(
    title="水库供水教学模拟",
    description="固定时间步水量平衡模拟（教学用途，不替代现实供水决策）",
    version="1.0.0",
)

# 允许 Angular 开发服务器（localhost:4200）跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables() -> None:
    # 教学项目直接建表；生产环境应使用 Alembic 迁移
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "note": "教学模拟，不连接真实闸门"}


app.include_router(scenarios.router)
app.include_router(simulate.router)
