"""Donote API 애플리케이션 진입점."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 라우터 임포트
from app.auth.router import router as auth_router
from app.transactions.router import router as transactions_router
from app.categories.router import router as categories_router
from app.statistics.router import router as statistics_router
from app.budgets.router import router as budgets_router
from app.settlements.router import router as settlements_router
from app.csv_import.router import router as csv_import_router
from app.notifications.router import router as notifications_router

app = FastAPI(
    title="Donote API",
    description="개인 재무 관리 + 더치페이 정산 API",
    version="0.1.0",
)

# 1. CORS 미들웨어 설정 (웹 프론트엔드 연동 시 필수)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: 실제 운영 환경에서는 프론트엔드 도메인(예: "https://donote.com")으로 변경하세요.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 라우터 등록 (버전 관리 및 Swagger UI 가독성을 위한 prefix, tags 추가)
api_prefix = "/api/v1"

app.include_router(auth_router, prefix=f"{api_prefix}/auth", tags=["Auth"])
app.include_router(transactions_router, prefix=f"{api_prefix}/transactions", tags=["Transactions"])
app.include_router(categories_router, prefix=f"{api_prefix}/categories", tags=["Categories"])
app.include_router(statistics_router, prefix=f"{api_prefix}/statistics", tags=["Statistics"])
app.include_router(budgets_router, prefix=f"{api_prefix}/budgets", tags=["Budgets"])
app.include_router(settlements_router, prefix=f"{api_prefix}/settlements", tags=["Settlements"])
app.include_router(csv_import_router, prefix=f"{api_prefix}/csv-import", tags=["CSV Import"])
app.include_router(notifications_router, prefix=f"{api_prefix}/notifications", tags=["Notifications"])


@app.get("/", tags=["Health Check"])
def root():
    """API 상태 확인 엔드포인트."""
    return {"message": "Donote API is running"}