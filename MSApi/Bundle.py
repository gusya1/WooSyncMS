from typing import Optional

from MSApi.Assortment import Assortment
from MSApi.ObjectMS import check_init
from MSApi.PriceType import PriceType
from MSApi.ProductFolder import ProductFolder


class Bundle(Assortment):

    def __init__(self, json):
        super().__init__(json)

    @check_init
    def get_productfolder(self) -> Optional[ProductFolder]:
        result = self._json.get('productFolder')
        if result is None:
            return None
        return ProductFolder(result)
