from typing import Optional

from MSApi.Assortment import Assortment
from MSApi.Product import Product
from MSApi.PriceType import PriceType
from MSApi.ProductFolder import ProductFolder


class Variant(Assortment):

    def __init__(self, json):
        super().__init__(json)

    def get_product(self):
        return Product(self._json.get('product'))
