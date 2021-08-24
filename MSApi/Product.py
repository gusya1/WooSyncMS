from MSApi.ObjectMS import ObjectMS, SubObjectMS


class SalePrice(SubObjectMS):
    def __init__(self, json):
        super().__init__(json)


class Product(ObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def __str__(self):
        self.get_name()

    def get_name(self):
        return self._json.get('name')

    def get_id(self):
        return self._json.get('id')

    def get_description(self):
        return self._json.get('description')

    def gen_sale_prices(self):
        json_sale_prices = self._json.get('salePrices')
        if json_sale_prices is None:
            return
        for json_sale_price in json_sale_prices:
            yield SalePrice(json_sale_price)
