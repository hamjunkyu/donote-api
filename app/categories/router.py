from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
# 프로젝트 환경에 맞게 인증 의존성 경로 수정 필요
from app.dependencies import get_current_user
from app.models import User 

from .schemas import CategoryResponse, CategoryCreate, CategoryUpdate
from . import service

router = APIRouter(prefix="/api/categories", tags=["Categories"])

@router.get("/", response_model=List[CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.get_categories(db, current_user.id)

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return service.create_category(db, current_user.id, data)

@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    category = service.update_category(db, current_user.id, category_id, data)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="수정 권한이 없거나 존재하지 않는 카테고리입니다."
        )
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        success = service.delete_category(db, current_user.id, category_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="삭제 권한이 없거나 존재하지 않는 카테고리입니다."
            )
    except ValueError as e:
        if str(e) == "CATEGORY_IN_USE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="해당 카테고리와 연결된 데이터가 있어 삭제할 수 없습니다."
            )
        raise e