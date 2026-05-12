from pydantic import BaseModel, ConfigDict
import uuid

class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str

    model_config = ConfigDict(from_attributes=True)
