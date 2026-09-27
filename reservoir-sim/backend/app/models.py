"""场景表：把完整场景定义（ScenarioIn 的 JSON）存入 PostgreSQL。"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from .database import Base

# PostgreSQL 上用 JSONB，其它库（如测试用 SQLite）退化为普通 JSON
PayloadType = JSON().with_variant(JSONB, "postgresql")


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    payload = Column(PayloadType, nullable=False)  # ScenarioIn 的完整 JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())
