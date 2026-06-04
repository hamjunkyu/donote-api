from pydantic import BaseModel, ConfigDict, Field, computed_field
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

    @computed_field
    @property
    def is_system(self) -> bool:
        """시스템 기본 카테고리 여부 (user_id 없으면 시스템)."""
        return self.user_id is None