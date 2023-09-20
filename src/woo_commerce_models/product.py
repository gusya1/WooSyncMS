from enum import Enum
from typing import List

from pydantic import BaseModel


class ProductType(str, Enum):
    SIMPLE = "simple"
    GROUPED = "grouped"
    EXTERNAL = "external"
    VARIABLE = "variable"


class ProductMetaData(BaseModel):
    id: int
    key: str
    value: str


class Product(BaseModel):
    id: int
    type: ProductType
    meta_data: List[ProductMetaData]