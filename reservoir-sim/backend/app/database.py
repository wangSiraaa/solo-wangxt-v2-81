"""数据库连接。默认连接 PostgreSQL，可用环境变量 DATABASE_URL 覆盖。

教学部署：docker compose up db  即可启动 PostgreSQL（见仓库根目录 docker-compose.yml）。
自动化测试使用 SQLite（tests/conftest.py 会设置 DATABASE_URL）。
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://reservoir:reservoir@localhost:5432/reservoir",
)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
