
from typing import Union
from MSApi.MSApi import MSApi, PriceType, Product, SpecialPriceDiscount
from MSApi.CompanySettings import DiscountStrategy


class DiscountHandlerException(Exception):
    pass


class DiscountHandler:

    def __init__(self):
        self.__active_discounts: [SpecialPriceDiscount] = []
        for discount in MSApi.gen_special_price_discounts():
            if not discount.is_active():
                continue
            self.__active_discounts.append(discount)

        self.__default_price_type = MSApi.get_default_price_type()

    def get_default_price_type(self) -> PriceType:
        return self.__default_price_type

    def get_default_price_value(self, product: Product):
        for sale_price in product.gen_sale_prices():
            if sale_price.get_price_type() == self.__default_price_type:
                return sale_price.get_value()
        else:
            raise DiscountHandlerException(f"Default price type in {product} not found")

    def get_actual_price(self, product: Product, counterparty_group_tag: str) -> float:
        max_discount_percent: float = 0
        discount_price_types: [PriceType] = []

        for discount in self.__active_discounts:
            if self.__is_discount_included_agent_group(discount, counterparty_group_tag) \
                    and self.__is_discount_included_product(discount, product):
                if discount.is_use_price_type():
                    # TODO обработка параметра value
                    price_type = discount.get_special_price().get_price_type()
                    if price_type not in discount_price_types:
                        discount_price_types.append(price_type)
                else:
                    disc_percent = discount.get_discount_percent() or 0
                    if disc_percent > max_discount_percent:
                        max_discount_percent = disc_percent

        min_price = current_price = self.get_default_price_value(product)

        for sale_price in product.gen_sale_prices():
            value = sale_price.get_value()
            if sale_price.get_price_type() in discount_price_types:
                if min_price > value:
                    min_price = value

        percent_sale_price = current_price * (1 - max_discount_percent)
        if min_price > percent_sale_price:
            min_price = percent_sale_price

        return round(min_price * 100) / 100

    @staticmethod
    def __is_discount_included_agent_group(discount: SpecialPriceDiscount, agent_group: str) -> bool:
        return discount.is_all_agents() or (agent_group in discount.gen_agent_tags())

    @staticmethod
    def __is_discount_included_product(discount: SpecialPriceDiscount, product: Product) -> bool:
        if discount.is_all_products():
            return True
        for obj_meta in discount.gen_assortment():
            obj = MSApi.get_object_by_meta(obj_meta)
            if type(obj) is not Product:
                continue
            else:
                if obj == product:
                    return True
        for productfolder in discount.gen_productfolders():
            if productfolder == product.get_productfolder():
                return True
        return False




