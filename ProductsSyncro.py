
from MSApi.MSApi import MSApi, MSApiHttpException, Product, Variant, Bundle
from MSApi.MSLowApi import error_handler
from MSApi.properties import *

from DiscountHandler import DiscountHandler, DiscountHandlerException

from WcApi import WcApi
from exceptions import SyncroException, WcApiException
import logging

WC_ID_ATTR_NAME = 'wc_id'
IMPORT_FLAG_ATTR_NAME = 'Импортировать в Интернет-магазин'
SALE_GROUP_TAG = ''


def get_wc_prices(wc_product):
    """возвращает обычную цену и цену со скидкой из товара WooCommerce"""
    regular_price = wc_product.get('regular_price')
    if regular_price == '':
        regular_price = None
    else:
        regular_price = float(regular_price)
    sale_price = wc_product.get('sale_price')
    if sale_price == '':
        sale_price = None
    else:
        sale_price = float(sale_price)
    return regular_price, sale_price


class ProductsSyncro:

    def __init__(self, sale_group_tag):
        self.__sale_group_tag = sale_group_tag

        self.__import_flag_attribute = None
        self.__wc_id_attribute = None
        for attr in Product.gen_attributes_list():
            if attr.get_name() == IMPORT_FLAG_ATTR_NAME:
                self.__import_flag_attribute = attr
            if attr.get_name() == WC_ID_ATTR_NAME:
                self.__wc_id_attribute = attr

        if self.__import_flag_attribute is None:
            raise SyncroException("product attribute '{}' not found".format(IMPORT_FLAG_ATTR_NAME))
        if self.__wc_id_attribute is None:
            raise SyncroException("product attribute '{}' not found".format(WC_ID_ATTR_NAME))

        self.wc_products = list(WcApi.gen_all_wc_products())

        self.ms_products = list(Product.gen_list(
            filters=Filter.eq(self.__import_flag_attribute.get_meta().get_href(), True)))

        self.ms_bundles = []
        for ms_bundle in Bundle.gen_list():
            # FIXME исправить на фильтр когда зафиксят баг
            import_flag = ms_bundle.get_attribute_by_name(IMPORT_FLAG_ATTR_NAME)
            if import_flag is None:
                continue
            if not import_flag.get_value():
                continue
            self.ms_bundles.append(ms_bundle)

    def __get_wc_product_by_id(self, wc_id):
        for wc_product in self.wc_products:
            if wc_product['id'] == int(wc_id):
                return wc_product
        return None

    def find_duplicate_wc_products(self):
        """
        ищет повторяющиеся продукты и пишет о них в лог
        """
        dist_of_products = {}

        for ms_product in self.ms_products:
            wc_id = ms_product.get_attribute_by_name(WC_ID_ATTR_NAME)
            if wc_id is None:
                continue
            wc_id = wc_id.get_value()

            ms_id_list = dist_of_products.setdefault(wc_id, [])
            if ms_product not in ms_id_list:
                ms_id_list.append(ms_product)

        for ms_bundle in self.ms_bundles:
            wc_id = ms_bundle.get_attribute_by_name(WC_ID_ATTR_NAME)
            if wc_id is None:
                continue
            wc_id = wc_id.get_value()

            ms_id_list = dist_of_products.setdefault(wc_id, [])
            if ms_bundle not in ms_id_list:
                ms_id_list.append(ms_bundle)

        for wc_id, ms_product_list in dist_of_products.items():
            if len(ms_product_list) > 1:
                logging.warning("Product duplicates [{}]:\n\t{}".format(
                    wc_id,
                    "\n\t".join("{} ({})".format(product.get_id(), product.get_name()) for product in ms_product_list)))

        return

    def find_unsync_wc_products(self):
        """Ищет несинхронизированные продукты WC и пишет о них в лог"""

        assortment_wc_ids = set()
        for ms_product in self.ms_products:
            wc_id = ms_product.get_attribute_by_name(WC_ID_ATTR_NAME)
            if wc_id is None:
                continue
            assortment_wc_ids.add(int(ms_product.get_attribute_by_name(WC_ID_ATTR_NAME).get_value()))

        for ms_bundle in self.ms_bundles:
            ms_bundle: Bundle
            wc_id = ms_bundle.get_attribute_by_name(WC_ID_ATTR_NAME)
            if wc_id is None:
                continue
            assortment_wc_ids.add(int(wc_id.get_value()))

        for wc_product in self.wc_products:
            wc_id = wc_product.get('id')
            if wc_id not in assortment_wc_ids:
                logging.warning(
                    "WC Product unsyncronized: [{}] {}".format(wc_id, wc_product.get('name')))
                continue
            else:
                assortment_wc_ids.remove(wc_id)

        for wc_id in assortment_wc_ids:
            logging.warning("WC Product with \'{}\' id not found".format(wc_id))

    def create_new_products(self):
        """Создаёт новые продукты"""

        for ms_product in self.ms_products:
            ms_product: Product
            try:
                if ms_product.get_attribute_by_name(WC_ID_ATTR_NAME) is not None:
                    continue

                wc_put_data = {
                    'name': ms_product.get_name(),
                    'status': 'draft'
                }

                if ms_product.has_variants():
                    wc_put_data['type'] = "variable"
                    continue
                else:
                    wc_put_data['type'] = "simple"

                wc_put_data.update(self.__get_wc_put_data_prices(ms_product))

                wc_json = WcApi.post('products', data=wc_put_data)
                response = MSApi.auch_put(
                    "entity/product/{}".format(ms_product.get_id()),
                    json={
                        "attributes": [
                            {
                                'meta': self.__wc_id_attribute.get_meta().get_json(),
                                "value": str(wc_json.get('id'))
                            }
                        ]
                    })
                error_handler(response)
                logging.info("WC Product '{}' created".format(ms_product.get_name()))

                # if ms_product.has_variants():
                #     self.__create_new_wc_attributes(ms_product)

            except MSApiHttpException as e:
                logging.error(str(e))
            except SyncroException as e:
                logging.error(str(e))
            except WcApiException as e:
                logging.error(str(e))
            except DiscountHandlerException as e:
                logging.error(str(e))

    def create_new_bundles(self):
        """Создаёт новые комплекты как обычные продукта WC"""

        # FIXME исправить на фильтр когда зафиксят баг
        for ms_bundle in self.ms_bundles:
            try:
                ms_bundle: Bundle
                if ms_bundle.get_attribute_by_name(WC_ID_ATTR_NAME) is not None:
                    continue

                wc_put_data = {
                    'name': ms_bundle.get_name(),
                    'status': 'draft',
                    'type': 'simple'
                }

                wc_put_data.update(self.__get_wc_put_data_prices(ms_bundle))

                wc_json = WcApi.post('products', data=wc_put_data)
                response = MSApi.auch_put(
                    "entity/bundle/{}".format(ms_bundle.get_id()),
                    json={
                        "attributes": [
                            {
                                'meta': self.__wc_id_attribute.get_meta().get_json(),
                                "value": str(wc_json.get('id'))
                            }
                        ]
                    })
                error_handler(response)
                logging.info("WC Product '{}' created".format(ms_bundle.get_name()))

            except MSApiHttpException as e:
                logging.error(str(e))
            except SyncroException as e:
                logging.error(str(e))
            except WcApiException as e:
                logging.error(str(e))
            except DiscountHandlerException as e:
                logging.error(str(e))

    @staticmethod
    def create_new_characteristics():
        """Создаёт новые характеристики товаров"""
        wc_characteristics = WcApi.get("products/attributes")

        for ms_char in Variant.gen_characteristics_list():
            ms_char_name = ms_char.get_name()
            if ms_char_name in (wc_char.get('name') for wc_char in wc_characteristics):
                continue

            wc_post_data = {
                'name': ms_char_name,
            }

            WcApi.post('products/attributes', wc_post_data)
            logging.info("WC Product attribute \'{}\' created".format(ms_char_name))

    def sync_products(self):
        """Синхронизирует товары"""
        try:
            for ms_product in self.ms_products:
                ms_product: Product
                try:
                    wc_id = ms_product.get_attribute_by_name(WC_ID_ATTR_NAME)
                    if wc_id is None:
                        continue
                    wc_id = wc_id.get_value()

                    wc_product = self.__get_wc_product_by_id(wc_id)
                    if wc_product is None:
                        raise SyncroException("[{}] WC Product not found".format(wc_id))
                    wc_type = wc_product.get('type')
                    if wc_product.get('type') == 'variable':
                        if not ms_product.has_variants():
                            # TODO change to simple
                            raise SyncroException(
                                "[{}] Change variant product to simple is not implemented now".format(wc_id))
                        # TODO sync variant
                        raise SyncroException("[{}] Unsupported product type: {}".format(wc_id, wc_type))
                    elif wc_type != 'simple':
                        raise SyncroException("[{}] Unsupported product type: {}".format(wc_id, wc_type))
                    elif ms_product.has_variants():
                        # TODO change to variant
                        raise SyncroException(
                            "[{}] Change simple product to variant is not implemented now".format(wc_id))

                    wc_put_data = {}

                    wc_put_data.update(self.__sync_name(ms_product, wc_product))
                    wc_put_data.update(self.__sync_prices(ms_product, wc_product))

                    if wc_put_data:
                        WcApi.put(f'products/{wc_product.get("id")}', data=wc_put_data)

                except SyncroException as e:
                    logging.error(str(e))
                except DiscountHandlerException as e:
                    logging.error(str(e))
                except WcApiException as e:
                    logging.error(str(e))

        except MSApiHttpException as e:
            logging.error(str(e))

    def sync_bundles(self):
        """Синхронизирует комплекты"""
        try:
            for ms_bundle in self.ms_bundles:
                ms_bundle: Bundle
                try:
                    wc_id = ms_bundle.get_attribute_by_name(WC_ID_ATTR_NAME)
                    if wc_id is None:
                        continue
                    wc_id = wc_id.get_value()

                    wc_product = self.__get_wc_product_by_id(wc_id)
                    if wc_product is None:
                        raise SyncroException("[{}] WC Product not found".format(wc_id))
                    wc_type = wc_product.get('type')
                    if wc_product.get('type') == 'variable':
                        # TODO sync variant
                        raise SyncroException("[{}] Bundle cannot be variant".format(wc_id, wc_type))
                    elif wc_type != 'simple':
                        raise SyncroException("[{}] Unsupported product type: {}".format(wc_id, wc_type))

                    wc_put_data = {}

                    wc_put_data.update(self.__sync_name(ms_bundle, wc_product))
                    wc_put_data.update(self.__sync_prices(ms_bundle, wc_product))

                    if wc_put_data:
                        WcApi.put(f'products/{wc_id}', data=wc_put_data)

                except SyncroException as e:
                    logging.error(str(e))
                except DiscountHandlerException as e:
                    logging.error(str(e))
                except WcApiException as e:
                    logging.error(str(e))

        except MSApiHttpException as e:
            logging.error(str(e))

    @staticmethod
    def __sync_name(ms_object, wc_object):
        """Возвращает данные для обновления имени WC"""
        ms_name = ms_object.get_name()
        wc_name = wc_object.get('name')
        if ms_name != wc_name:
            logging.info("WC product [{}] name changed from \'{}\' to \'{}\'"
                         .format(wc_object.get('id'), wc_name, ms_name))
            return {'name': ms_name}
        else:
            return {}

    def __sync_prices(self, ms_object, wc_product):
        """Возвращает данные для обновления цен WC"""
        wc_regular_price, wc_sale_price = get_wc_prices(wc_product)
        wc_put_data = {}
        ms_regular_price = DiscountHandler.get_default_price_value(ms_object)
        ms_sale_price = DiscountHandler.get_actual_price(ms_object, self.__sale_group_tag)
        if ms_regular_price != wc_regular_price:
            wc_put_data['regular_price'] = str(ms_regular_price)
            logging.info("WC product [{}] regular price changed from {} to {}"
                         .format(wc_product.get('id'), wc_regular_price, ms_regular_price))

        if ms_sale_price == ms_regular_price:
            ms_sale_price = None

        if ms_sale_price != wc_sale_price:
            if ms_sale_price is None:
                wc_put_data['sale_price'] = ''
                logging.info("WC product [{}] sale price removed".format(wc_product.get('id')))
            else:
                wc_put_data['sale_price'] = str(ms_sale_price)
                logging.info("WC product [{}] sale price changed from {} to {}"
                             .format(wc_product.get('id'), wc_sale_price, ms_sale_price))
        return wc_put_data

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
