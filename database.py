from sqlalchemy import create_engine
from config import DB_PATH

engine = create_engine(DB_PATH, future=True)
