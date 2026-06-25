"""
utils/db/models/control_admin.py - Modèle CommandControl, toggle des commandes.
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from cogs.api.base import Base, TimestampMixin


class CommandControl(Base, TimestampMixin):
    __tablename__ = "command_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    command_name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)