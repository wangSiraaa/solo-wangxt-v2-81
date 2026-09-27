"""数据库配置。

优先连接 PostgreSQL（教学部署）；未设置 DATABASE_URL 时回退到本地 SQLite 文件，
便于课堂离线演示与单元测试。
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./reservoir.db",
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # 局部导入，避免循环依赖
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
