from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from uuid import UUID
from typing import Sequence
from .models import Category
from .schemas import CategoryCreate

class CategoryService:
    @staticmethod
    def get_categories(db: Session, user_id: UUID) -> Sequence[Category]:
        # 시스템 기본(None) 및 사용자 지정 카테고리 병합 조회
        stmt = select(Category).where(
            or_(Category.user_id == None, Category.user_id == user_id)
        )
        result = db.execute(stmt) # await 제거됨
        return result.scalars().all()

    @staticmethod
    def create_category(db: Session, user_id: UUID, data: CategoryCreate) -> Category:
        new_category = Category(
            user_id=user_id,
            name=data.name,
            type=data.type.value 
        )
        db.add(new_category)
        db.commit()          # await 제거됨
        db.refresh(new_category) # await 제거됨
        return new_category

    @staticmethod
    def delete_category(db: Session, user_id: UUID, category_id: UUID) -> bool:
        stmt = select(Category).where(
            and_(Category.id == category_id, Category.user_id == user_id)
        )
        result = db.execute(stmt) # await 제거됨
        category = result.scalar_one_or_none()
        
        if not category:
            return False
            
        db.delete(category)
        db.commit()          # await 제거됨
        return True