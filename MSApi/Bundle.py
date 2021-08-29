from typing import Optional

from MSApi.Assortment import Assortment
from MSApi.PriceType import PriceType
from MSApi.ProductFolder import ProductFolder


class Bundle(Assortment):

    def __init__(self, json):
        super().__init__(json)