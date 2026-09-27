"""测试准备：用 SQLite 代替 PostgreSQL（SQLAlchemy 对两者透明）。

必须在导入 app 之前设置 DATABASE_URL。
"""
import os

os.environ["DATABASE_URL"] = "sqlite:////tmp/reservoir_test.db"

# 每个测试会话开始前清库
if os.path.exists("/tmp/reservoir_test.db"):
    os.remove("/tmp/reservoir_test.db")

from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402, F401  （注册表结构）

Base.metadata.create_all(bind=engine)
