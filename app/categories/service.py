from sqlalchemy.orm import Session
from sqlalchemy import select, or_
from .models import Category
import uuid

def get_categories(db: Session, user_id: uuid.UUID):
    query = select(Category).where(
        or_(Category.user_id == None, Category.user_id == user_id)
    )
    categories = db.execute(query).scalars().all()
    
    # 기본 데이터가 없으면 자동 생성
    if not categories:
        cat1 = Category(name="식비", type="EXPENSE")
        cat2 = Category(name="월급", type="INCOME")
        db.add_all([cat1, cat2])
        db.commit()
        db.refresh(cat1)
        db.refresh(cat2)
        categories = [cat1, cat2]
        
    return categories
