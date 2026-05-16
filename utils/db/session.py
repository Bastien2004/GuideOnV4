from sqlalchemy.orm import sessionmaker
from utils.db.engine import engine

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)