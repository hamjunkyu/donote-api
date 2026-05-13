from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal 
from app.categories.service import init_default_categories

# 라우터 통합 등록
from app.auth.router import router as auth_router
from app.transactions.router import router as transactions_router
from app.categories.router import router as categories_router
from app.csv_import.router import router as csv_import_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 시작 시 실행될 로직:
    - 기본 카테고리가 없는 경우 자동으로 생성 (Seeding 호출)
    """
    db = SessionLocal()
    try:
        # 지적하신 대로 시작 시점에 기본 카테고리를 생성합니다.
        init_default_categories(db)
    finally:
        db.close()
    yield

def create_app() -> FastAPI:
    app = FastAPI(
        title="Donote API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API v1 라우터 등록 (충돌 지점 해결)
    api_v1_prefix = "/api/v1"
    app.include_router(auth_router, prefix=f"{api_v1_prefix}/auth", tags=["Auth"])
    app.include_router(categories_router, prefix=f"{api_v1_prefix}/categories", tags=["Categories"])
    app.include_router(transactions_router, prefix=f"{api_v1_prefix}/transactions", tags=["Transactions"])
    app.include_router(csv_import_router, prefix=f"{api_v1_prefix}/csv-import", tags=["CSV Import"])

    return app

app = create_app()