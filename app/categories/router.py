from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.auth.dependencies import get_current_user
from . import schemas, service

router = APIRouter(prefix="/api/categories", tags=["Categories"])

@router.get("/", response_model=List[schemas.CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    return service.get_categories(db, current_user.id)
