from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
# 1. 지적하신 대로 auth 모듈 내부의 정확한 경로로 수정 완료
from app.auth.dependencies import get_current_user 
from .schemas import CategoryResponse, CategoryCreate, CategoryUpdate
from . import service

router = APIRouter(prefix="/api/categories", tags=["Categories"])

@router.get("/", response_model=List[CategoryResponse], summary="카테고리 목록 조회")
def list_categories(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    시스템 기본 카테고리와 현재 로그인한 사용자의 커스텀 카테고리를 모두 조회합니다.
    """
    return service.get_categories(db, current_user.id)

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED, summary="카테고리 생성")
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    현재 사용자를 소유자로 하는 새로운 카테고리를 생성합니다.
    """
    return service.create_category(db, current_user.id, data)

@router.patch("/{category_id}", response_model=CategoryResponse, summary="카테고리 수정")
def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    사용자 정의 카테고리의 이름을 수정합니다. 
    시스템 기본 카테고리이거나 본인 소유가 아니면 403 에러를 반환합니다.
    """
    category = service.update_category(db, current_user.id, category_id, data)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="수정 권한이 없거나 존재하지 않는 카테고리입니다."
        )
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="카테고리 삭제")
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    사용자 정의 카테고리를 삭제합니다.
    시스템 기본 카테고리이거나 본인 소유가 아니면 403 에러를 반환합니다.
    """
    success = service.delete_category(db, current_user.id, category_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="삭제 권한이 없거나 존재하지 않는 카테고리입니다."
        )
    return None