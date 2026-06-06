from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from sqlalchemy.exc import IntegrityError
from uuid import UUID
from typing import Sequence, Optional

from .models import Category
from .schemas import CategoryCreate, CategoryUpdate
from app.shared.exceptions import ConflictError

def init_default_categories(db: Session) -> None:
    """
    시스템 기본 카테고리 시드 로직.
    main.py의 lifespan 이벤트 등에서 1회 호출하여 사용.
    """
    stmt = select(Category).where(Category.user_id.is_(None))
    existing = db.execute(stmt).scalars().first()
    
    if not existing:
        default_categories = [
            # 지출 (11)
            {"name": "식비", "type": "EXPENSE"},
            {"name": "카페/간식", "type": "EXPENSE"},
            {"name": "교통", "type": "EXPENSE"},
            {"name": "생활/마트", "type": "EXPENSE"},
            {"name": "쇼핑", "type": "EXPENSE"},
            {"name": "주거/통신", "type": "EXPENSE"},
            {"name": "의료/건강", "type": "EXPENSE"},
            {"name": "문화/여가", "type": "EXPENSE"},
            {"name": "교육", "type": "EXPENSE"},
            {"name": "경조사/회비", "type": "EXPENSE"},
            {"name": "기타", "type": "EXPENSE"},
            # 수입 (4)
            {"name": "급여/알바", "type": "INCOME"},
            {"name": "용돈", "type": "INCOME"},
            {"name": "금융소득", "type": "INCOME"},
            {"name": "기타", "type": "INCOME"},
        ]
        
        for cat_data in default_categories:
            new_cat = Category(
                user_id=None,
                name=cat_data["name"],
                type=cat_data["type"] 
            )
            db.add(new_cat)
        db.commit()

def get_categories(db: Session, user_id: UUID, type: Optional[str] = None) -> Sequence[Category]:
    stmt = select(Category).where(
        or_(Category.user_id.is_(None), Category.user_id == user_id)
    )
    if type is not None:
        stmt = stmt.where(Category.type == type)
    stmt = stmt.order_by(Category.type, Category.name)
    result = db.execute(stmt)
    return result.scalars().all()

def create_category(db: Session, user_id: UUID, data: CategoryCreate) -> Category:
    new_category = Category(
        user_id=user_id,
        name=data.name,
        type=data.type.value
    )
    db.add(new_category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("이미 같은 이름의 카테고리가 있습니다.")
    db.refresh(new_category)
    return new_category

def update_category(db: Session, user_id: UUID, category_id: UUID, data: CategoryUpdate) -> Optional[Category]:
    stmt = select(Category).where(
        and_(Category.id == category_id, Category.user_id == user_id)
    )
    result = db.execute(stmt)
    category = result.scalar_one_or_none()
    
    if not category:
        return None 
        
    category.name = data.name
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("이미 같은 이름의 카테고리가 있습니다.")
    db.refresh(category)
    return category

def delete_category(db: Session, user_id: UUID, category_id: UUID) -> bool:
    stmt = select(Category).where(
        and_(Category.id == category_id, Category.user_id == user_id)
    )
    result = db.execute(stmt)
    category = result.scalar_one_or_none()
    
    if not category:
        return False
        
    db.delete(category)
    try:
        db.commit()          
        return True
    except IntegrityError:
        db.rollback()
        # 사용 중인 카테고리(거래/예산/목표 참조)는 삭제 불가
        raise ConflictError("사용 중인 카테고리는 삭제할 수 없습니다.") 