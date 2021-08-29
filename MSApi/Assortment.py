from typing import Optional

from MSApi.ObjectMS import ObjectMS, SubObjectMS
from MSApi.PriceType import PriceType
from MSApi.ProductFolder import ProductFolder


class SalePrice(SubObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def get_value(self) -> float:
        return self._json.get('value')/100

    def get_price_type(self) -> PriceType:
        return PriceType(self._json.get('priceType'))


class Assortment(ObjectMS):

    def __init__(self, json):
        super().__init__(json)

    def get_id(self) -> str:
        return self._json.get('id')

    def get_name(self) -> str:
        return self._json.get('name')

    def gen_sale_prices(self):
        """Цены продажи."""
        json_sale_prices = self._json.get('salePrices')
        if json_sale_prices is None:
            return
        for json_sale_price in json_sale_prices:
            yield SalePrice(json_sale_price)
