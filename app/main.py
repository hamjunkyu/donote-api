"""Donote API 애플리케이션 진입점."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.auth.router import router as auth_router
from app.budgets.router import router as budgets_router
from app.categories.router import router as categories_router
from app.categories.service import init_default_categories
from app.csv_import.router import router as csv_import_router
from app.database import SessionLocal
from app.goals.router import router as goals_router
from app.notifications.router import router as notifications_router
from app.settlements.router import router as settlements_router
from app.statistics.router import router as statistics_router
from app.transactions.router import router as transactions_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 시스템 기본 카테고리 시드.

    시드 실패가 startup 전체를 죽이지 않도록 예외를 로깅만 하고 진행한다.
    """
    db = SessionLocal()
    try:
        init_default_categories(db)
    except Exception:
        logger.exception("기본 카테고리 시드 실패")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Donote API",
    description="개인 재무 관리 + 더치페이 정산 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(statistics_router)
app.include_router(budgets_router)
app.include_router(settlements_router)
app.include_router(csv_import_router)
app.include_router(notifications_router)
app.include_router(goals_router)


@app.get("/")
def root():
    """API 상태 확인 엔드포인트."""
    return {"message": "Donote API is running"}
