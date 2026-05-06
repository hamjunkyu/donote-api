from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from .schemas import CategoryResponse, CategoryCreate
from .service import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    user_id: UUID, 
    db: Session = Depends(get_db) # 동기 세션 주입
):
    return CategoryService.get_categories(db, user_id) # await 제거됨

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    user_id: UUID,
    data: CategoryCreate,
    db: Session = Depends(get_db)
):
    return CategoryService.create_category(db, user_id, data) # await 제거됨

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db)
):
    success = CategoryService.delete_category(db, user_id, category_id) # await 제거됨
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="삭제 권한이 없거나 존재하지 않는 카테고리입니다."
        )