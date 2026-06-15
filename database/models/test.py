from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from database.database import Base


class TestTable(Base):

    __tablename__ = "test_table"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    discord_id: Mapped[int] = mapped_column(
        BigInteger
    )