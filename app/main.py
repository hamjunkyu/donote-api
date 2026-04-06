"""Donote API 애플리케이션 진입점."""

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.transactions.router import router as transactions_router
from app.categories.router import router as categories_router
from app.statistics.router import router as statistics_router
from app.budgets.router import router as budgets_router
from app.settlements.router import router as settlements_router
from app.csv_import.router import router as csv_import_router

app = FastAPI(
    title="Donote API",
    description="개인 재무 관리 + 더치페이 정산 API",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(statistics_router)
app.include_router(budgets_router)
app.include_router(settlements_router)
app.include_router(csv_import_router)


@app.get("/")
def root():
    """API 상태 확인 엔드포인트."""
    return {"message": "Donote API is running"}
