from typing import Optional

from MSApi.ObjectMS import ObjectMS
from MSApi.Assortment import Assortment
from MSApi.Product import Product
from MSApi.PriceType import PriceType
from MSApi.ProductFolder import ProductFolder


class Characteristic(ObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def get_id(self) -> str:
        return self._json.get('id')

    def get_name(self) -> str:
        return self._json.get('name')

    def get_value(self) -> str:
        return self._json.get('value')


class Variant(Assortment):

    def __init__(self, json):
        super().__init__(json)

    def get_product(self):
        return Product(self._json.get('product'))

    def gen_characteristics(self):
        json_characteristics = self._json.get('characteristics')
        if json_characteristics is None:
            return
        for json_characteristic in json_characteristics:
            yield Characteristic(json_characteristic)
