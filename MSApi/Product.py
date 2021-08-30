from typing import Optional

from MSApi.Assortment import Assortment
from MSApi.ProductFolder import ProductFolder


class Product(Assortment):

    def __init__(self, json):
        super().__init__(json)

    def __str__(self):
        self.get_name()

    def get_description(self) -> Optional[str]:
        return self._json.get('description')

    def get_productfolder(self) -> Optional[ProductFolder]:
        """Группа Товара"""
        result = self._json.get('productFolder')
        if result is None:
            return None
        return ProductFolder(result)

    def get_variants_count(self) -> int:
        return int(self._json.get('variantsCount'))

    def get_article(self) -> Optional[str]:
        return self._json.get('article')

    def has_variants(self) -> bool:
        return self.get_variants_count() > 1