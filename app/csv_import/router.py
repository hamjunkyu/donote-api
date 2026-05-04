import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.database import get_db
from .schemas import ImportResult
from .service import parse_csv_content, process_csv_import

router = APIRouter(prefix="/api/import", tags=["CSV Import"])


@router.post("/csv", response_model=ImportResult)
async def import_csv_data(
    user_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    CSV 파일을 업로드 받아 중복 여부를 검사하고 새로운 데이터의 해시를 import_hashes 테이블에 저장합니다.
    중복을 통과한 유효한 데이터 목록은 valid_rows에 담아 반환합니다.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")
        
    try:
        # 파일을 비동기적으로 읽기
        content = await file.read()
        
        # 인코딩 자동 감지 및 폴백(Fallback) 로직
        # 1. UTF-8 (BOM 포함) 시도
        try:
            decoded_content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            # 2. 실패 시 한국 엑셀 기본 인코딩(cp949) 시도
            decoded_content = content.decode("cp949")
            
        # 동기 제너레이터로 파싱
        row_generator = parse_csv_content(decoded_content)
        
        # 서비스 로직에 위임하여 DB 처리 및 중복 검증 진행
        result = process_csv_import(db=db, user_id=user_id, rows=row_generator)
        
        return result
        
    except ValidationError as e:
        # Pydantic 타입 검증 실패 시 상세 에러 반환
        raise HTTPException(status_code=422, detail=f"CSV 데이터 형식 오류 (날짜 및 금액 형식을 확인하세요): {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV 파일 처리 중 서버 오류가 발생했습니다: {str(e)}")