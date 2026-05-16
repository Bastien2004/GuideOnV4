import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)