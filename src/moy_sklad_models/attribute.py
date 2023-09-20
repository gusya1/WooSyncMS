from typing import Union

from pydantic import BaseModel

from model_types import UUID, Meta


class AttributeValueObject(BaseModel):
    meta: Meta
    name: str


class Attribute(BaseModel):
    id: UUID
    meta: Meta
    name: str
    value: Union[str, bool, int, float, AttributeValueObject]
