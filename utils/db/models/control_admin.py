from datetime import datetime
from sqlalchemy import Boolean, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from utils.db.base import Base  # ← .base import Base

class CommandControl(Base):  # ← Base avec B majuscule
    __tablename__ = "command_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now()
    )