from WcApi import *
from Reporter import *
from MSApi.MSApi import *
from MSApi.properties import *
from MSApi.Variant import *
from MSApi.Product import Product
from MSApi.Service import Service
from MSApi.Bundle import Bundle
from MSApi.DiscountHandler import DiscountHandler
from exceptions import *
from typing import Union

reporter = Reporter()


def get_product_by_id(product_id, **kwargs):
    response = MSApi.auch_get(f'entity/product/{product_id}', **kwargs)
    error_handler(response)
    return Product(response.json())


class NewAssortmentCreator:

    def __init__(self, wc_products: {}, sale_group_tag):
        self.__productfolder_ids_blacklist = []
        self.__assortment_ids_blacklist = []
        self.__sale_group_tag = sale_group_tag

        self.__wc_products = wc_products
        self.__sync_wc_products = {}  # MS_href, WC_id
        for wc_product in self.__wc_products:
            product_wooms_href = get_wooms_href(wc_product)
            if product_wooms_href is not None:
                self.__sync_wc_products[product_wooms_href] = wc_product.get('id')
            if wc_product.get('type') == 'variable':
                for wc_variation in gen_all_wc_variations(wc_product.get('id')):
                    variation_wooms_href = get_wooms_href(wc_variation)
                    if variation_wooms_href is not None:
                        self.__sync_wc_products[variation_wooms_href] = wc_variation.get('id')

        Reporter.add_report_group('new_variants', "New variants created")
        Reporter.add_report_group('new_products', "New products created")
        Reporter.add_report_group('errors', "Errors")

    def get_sync_wc_products(self):
        return self.__sync_wc_products

    def set_productfolder_ids_blacklist(self, blacklist: []):
        self.__productfolder_ids_blacklist = blacklist.copy()

    def set_assortment_ids_blacklist(self, blacklist: []):
        self.__assortment_ids_blacklist = blacklist.copy()

    def create_new_wc_products(self):

        self.__create_new_wc_variants()
        self.__create_new_wc_products()
        self.__create_new_wc_services()
        self.__create_new_wc_bundles()

    def create_new_product(self, ms_id):
        ms_product = get_product_by_id(ms_id)
        return "Product added {}".format(self.__create_new_wc_product(ms_product))

    def __create_new_wc_variants(self):
        for ms_variation in Variant.gen_list():
            if not self.__check_assortment(ms_variation):
                continue
            wc_product_id = self.__sync_wc_products.get(ms_variation.get_product().get_meta().get_href())
            # все модификации, которых нет на сайте, но чей родитель есть
            wc_product = WcApi.get(f'products/{wc_product_id}')
            self.__create_wc_variant(ms_variation, wc_product)

    # @except_discount_exception
    def __create_new_wc_products(self):
        for ms_product in Product.gen_list(expand=Expand('productFolder')):
            try:
                self.__create_new_wc_product(ms_product)
            except CheckAssortmentException:
                continue

    def __create_new_wc_product(self, ms_product):
        self.__check_assortment(ms_product)
        wc_put_data = {
            'status': 'draft',
            'meta_data': [
                {
                    'key': 'wooms_href',
                    'value': ms_product.get_meta().get_href()
                }
            ]
        }
        wc_put_data |= self.__get_wc_put_data_prices(ms_product)
        if ms_product.has_variants():
            wc_put_data['type'] = 'variable'
        article = ms_product.get_article()
        if article is not None:
            wc_put_data['sku'] = article

        wc_put_data['name'] = ms_product.get_name()

        response = WcApi.post('products', wc_put_data)
        Reporter.append_report('new_products', '"{}"'.format(ms_product.get_name()))
        if response is None:
            raise SyncroException("WcApi post method return None")

        wc_product_id = response.get('id')
        if ms_product.has_variants():
            self.__create_new_wc_variations(wc_product_id, ms_product.get_id())
        return wc_product_id

    # @except_discount_exception
    def __create_new_wc_services(self):
        for ms_service in Service.gen_list(expand=Expand('productFolder')):
            try:
                self.__check_assortment(ms_service)

                wc_put_data = {
                    'status': 'draft',
                    'virtual': True,
                    'meta_data': [
                        {
                            'key': 'wooms_href',
                            'value': ms_service.get_meta().get_href()
                        }
                    ]
                }
                wc_put_data |= self.__get_wc_put_data_prices(ms_service)
                wc_put_data['name'] = ms_service.get_name()

                WcApi.post('products', wc_put_data)
                Reporter.append_report('new_products', '"{}"'.format(ms_service.get_name()))
            except CheckAssortmentException:
                continue

    # @except_discount_exception
    def __create_new_wc_bundles(self):
        for ms_bundle in Bundle.gen_list(expand=Expand('productFolder')):
            try:
                self.__check_assortment(ms_bundle)

                wc_put_data = {
                    'status': 'draft',
                    'meta_data': [
                        {
                            'key': 'wooms_href',
                            'value': ms_bundle.get_meta().get_href()
                        }
                    ]
                }
                wc_put_data |= self.__get_wc_put_data_prices(ms_bundle)
                wc_put_data['name'] = ms_bundle.get_name()

                WcApi.post('products', wc_put_data)
                Reporter.append_report('new_products', '"{}"'.format(ms_bundle.get_name()))
            except CheckAssortmentException:
                continue

    def __create_new_wc_variations(self, wc_product_id, ms_product_id):
        all_characteristics: {str: [Characteristic]} = {}
        for ms_variant in Variant.gen_list(filters=Filter.eq('productid', ms_product_id)):
            for characteristic in ms_variant.gen_characteristics():
                all_characteristics.setdefault(characteristic.get_name(), []).append(characteristic)

        list_wc_attributes = []
        for name, ms_characteristic_list in all_characteristics:
            characteristic_values = [str]
            for ms_characteristic in ms_characteristic_list:
                characteristic_values.append(ms_characteristic.get_value())
            list_wc_attributes.append({
                "name": name,
                "visible": True,
                "variation": True,
                "options": characteristic_values
            })

        wc_put_data = {'attributes': list_wc_attributes}
        wc_product = WcApi.put(f'products/{wc_product_id}', wc_put_data)

        for ms_variant in Variant.gen_list(filters=Filter.eq('productid', ms_product_id)):
            self.__create_wc_variant(ms_variant, wc_product)

    # @except_discount_exception
    def __create_wc_variant(self, ms_variant, wc_product):
        wc_variant_put_data = {
            'status': 'draft',
            'meta_data': [
                {
                    'key': 'wooms_href',
                    'value': ms_variant.get_meta().get_href()
                }
            ]
        }
        wc_variant_put_data |= self.__get_wc_put_data_prices(ms_variant)

        report_attributes_strings = []
        attributes_list = []
        for characteristic in ms_variant.gen_characteristics():
            for wc_attr in wc_product.get('attributes'):
                if wc_attr.get('name') == characteristic.get_name():
                    break
            else:
                raise SyncroException(f"Characteristic {characteristic.get_name()} not found")
            attributes_list.append({
                'id': wc_attr.get('id'),
                'option': characteristic.get_value()
            })
            report_attributes_strings.append(f'"{characteristic.get_name()}" : {characteristic.get_value()}')
        wc_variant_put_data['attributes'] = attributes_list
        WcApi.put(f'products/{wc_product.get(id)}/variations', wc_variant_put_data)
        Reporter.append_report('new_variants',
                               'In product "{}" with attributes:\n{}'.format(ms_variant.get_name(),
                                                                             "\n\t".join(
                                                                                 report_attributes_strings)))

    def __get_wc_put_data_prices(self, ms_object,
                                 wc_regular_price: int = None,
                                 wc_sale_price: int = None):
        """вытаскивает из объекта МС обычную и скидочную цену, сравнивает с ценами WC
        и возвращает цены для отправки на сайт"""
        wc_put_data = {}
        ms_regular_price = DiscountHandler.get_default_price_value(ms_object)
        ms_sale_price = DiscountHandler.get_actual_price(ms_object, self.__sale_group_tag)
        if ms_regular_price != wc_regular_price:
            wc_put_data['regular_price'] = str(ms_regular_price)
        if ms_sale_price == ms_regular_price:
            ms_sale_price = None

        if ms_sale_price != wc_sale_price:
            if ms_sale_price is None:
                wc_put_data['sale_price'] = ''
            else:
                wc_put_data['sale_price'] = str(ms_sale_price)
        return wc_put_data

    def __check_assortment(self, ms_object: Union[Product, Service, Bundle, Variant]) -> None:
        """проверяет пеобходимость сознаия нового товара"""
        wc_product_id = self.__sync_wc_products.get(ms_object.get_meta().get_href())
        if wc_product_id is not None:
            raise SyncroException(f"Assortment already append: \"{wc_product_id}\"")
        if ms_object.get_meta().get_href() in self.__assortment_ids_blacklist:
            raise SyncroException(f"Assortment in blacklist: \"{ms_object.get_id()}\"")
        if type(ms_object) in [Product, Service, Bundle]:
            productfolder = ms_object.get_productfolder()
            if productfolder is None:
                return
            if productfolder.get_id() in self.__productfolder_ids_blacklist:
                raise SyncroException(f"Assortment`s productfolder in blacklist: \"{ms_object.get_id()}\"")
        else:
            # проверяем есть ли на сайте родитель
            wc_product_id = self.__sync_wc_products.get(ms_object.get_product().get_meta().get_href())
            if wc_product_id is None:
                raise SyncroException(f"Parent of modification not found: \"{ms_object.get_id()}\"")
        return
