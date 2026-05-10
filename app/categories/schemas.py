from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from enum import Enum
from typing import Optional

class CategoryType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50, description="카테고리 이름")
    type: CategoryType

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: str = Field(..., max_length=50, description="수정할 카테고리 이름")

class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: Optional[UUID] = None