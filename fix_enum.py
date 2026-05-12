import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url, isolation_level="AUTOCOMMIT")

with engine.connect() as conn:
    conn.execute(text("ALTER TYPE settlement_status RENAME VALUE 'IN_PROGRESS' TO 'PENDING'"))
    print("Enum renamed successfully.")
