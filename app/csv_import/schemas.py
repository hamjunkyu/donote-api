from datetime import date
from pydantic import BaseModel, Field


class CSVRowData(BaseModel):
    """CSV 파일의 단일 행 데이터를 검증하는 스키마입니다."""
    row_number: int = Field(..., description="CSV 파일 내의 행 번호")
    transaction_date: date = Field(..., description="거래 일자 (YYYY-MM-DD 형식)")
    amount: float = Field(..., description="거래 금액")
    memo: str = Field(default="", description="거래 메모")


class ImportResult(BaseModel):
    """CSV 가져오기 작업의 최종 결과를 반환하는 스키마입니다."""
    total_rows: int = Field(default=0, description="전체 처리된 행의 수")
    imported_count: int = Field(default=0, description="새롭게 해시가 등록된(중복이 아닌) 행의 수")
    duplicate_count: int = Field(default=0, description="중복으로 인해 건너뛴 행의 수")
    errors: list[str] = Field(default_factory=list, description="처리 중 발생한 오류 메시지 목록")
    valid_rows: list[CSVRowData] = Field(
        default_factory=list, 
        description="중복 검사를 통과한 유효한 데이터 목록"
    )