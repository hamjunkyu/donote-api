from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
# 인증 기능이 분리된 아키텍처에 맞추어 auth 모듈 내부로 경로 교정
from app.auth.dependencies import get_current_user 
from .schemas import ImportResult
from .service import parse_csv_content, process_csv_import

router = APIRouter(prefix="/api/import", tags=["CSV Import"])

@router.post("/csv", response_model=ImportResult)
async def import_csv_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    CSV 파일을 업로드 받아 중복 여부를 검사하고 새로운 데이터의 해시를 저장합니다.
    중복을 통과한 유효한 데이터는 카테고리 텍스트 자동 매칭을 거쳐 transactions 테이블에 일괄 등록됩니다.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")
        
    try:
        content = await file.read()
        
        try:
            decoded_content = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded_content = content.decode("cp949")
            
        row_generator = parse_csv_content(decoded_content)
        result = process_csv_import(db, current_user.id, row_generator)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV 처리 중 오류 발생: {str(e)}")