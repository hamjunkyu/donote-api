from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from .schemas import ImportResult
from .service import process_csv_import

router = APIRouter(prefix="/api/import", tags=["CSV Import"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_ROWS = 1000


@router.post("/csv", response_model=ImportResult)
async def import_csv_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """CSV 파일을 업로드 받아 중복 검사 후 유효한 거래를 일괄 등록한다.

    날짜·금액·카테고리 오류 행은 건너뛰고 결과의 errors 에 행 번호와 함께 기록한다.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV 파일만 업로드 가능합니다.",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="파일 크기는 5MB를 초과할 수 없습니다.",
        )

    try:
        decoded_content = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded_content = content.decode("cp949")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="파일 인코딩을 해석할 수 없습니다 (UTF-8 또는 CP949).",
            )

    if decoded_content.strip().count("\n") > MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"한 번에 최대 {MAX_ROWS}행까지 가능합니다.",
        )

    return process_csv_import(db, current_user.id, decoded_content)