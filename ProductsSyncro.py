
from MSApi.MSApi import MSApi, MSApiException, MSApiHttpException, Product, Service, Bundle, Variant
from MSApi.MSLowApi import error_handler
from MSApi.mixin import AttributeMixin
from MSApi.properties import *
from requests.exceptions import RequestException, ConnectTimeout
from DiscountHandler import DiscountHandler, DiscountHandlerException
from Reporter import Reporter
from WcApi import WcApi, get_wooms_href
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

    def find_duplicate_wc_products(self):
        """ищет повторяющиеся продукты и пишет о них в лог"""
        filters = Filter.eq(self.__import_flag_attribute.get_meta().get_href(), True)
        filters += Filter.exists(self.__wc_id_attribute.get_meta().get_href(), True)

        duplicates = {}
        for ms_assort_1 in MSApi.gen_products(filters=filters, cached=True):
            wc_id_1 = ms_assort_1.get_attribute_by_name(WC_ID_ATTR_NAME).get_value()
            if wc_id_1 is None:
                continue

            for ms_assort_2 in MSApi.gen_products(filters=filters, cached=True):
                if ms_assort_2.get_id() == ms_assort_1.get_id():
                    continue

                wc_id_2 = ms_assort_2.get_attribute_by_name(WC_ID_ATTR_NAME).get_value()
                if wc_id_2 is None:
                    continue

                if wc_id_1 == wc_id_2:
                    if wc_id_1 not in duplicates:
                        duplicates[wc_id_1] = [ms_assort_1, ms_assort_2]
                    else:
                        if ms_assort_1 not in duplicates[wc_id_1]:
                            duplicates[wc_id_1].append(ms_assort_1)
                        if ms_assort_2 not in duplicates[wc_id_1]:
                            duplicates[wc_id_1].append(ms_assort_2)

        for wc_id, product_list in duplicates.items():
            logging.warning("Product duplicates [{}]:\n\t{}".format(
                wc_id,
                "\n\t".join("{} ({})".format(product.get_id(), product.get_name()) for product in product_list)))

        return

    def find_unsync_wc_products(self):
        """Ищет несинхронизированные продукты WC и пишет о них в лог"""
        filters = Filter.eq(self.__import_flag_attribute.get_meta().get_href(), True)
        filters += Filter.exists(self.__wc_id_attribute.get_meta().get_href(), True)

        assortment_wc_ids = set()
        for ms_product in MSApi.gen_products(filters=filters, cached=True):
            assortment_wc_ids.add(int(ms_product.get_attribute_by_name(WC_ID_ATTR_NAME).get_value()))

        for wc_product in WcApi.gen_all_wc_products(cached=True):
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
        filters = Filter.eq(self.__import_flag_attribute.get_meta().get_href(), True)
        filters = filters + Filter.exists(self.__wc_id_attribute.get_meta().get_href(), False)

        for ms_product in MSApi.gen_products(filters=filters):
            try:
                ms_product: Product

                wc_put_data = {
                    'name': ms_product.get_name(),
                    'status': 'draft'
                }

                if ms_product.has_variants():
                    wc_put_data['type'] = "variable"
                else:
                    wc_put_data['type'] = "simple"

                wc_put_data |= self.__get_wc_put_data_prices(ms_product)

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
            filters = Filter.eq(self.__import_flag_attribute.get_meta().get_href(), True)
            filters += Filter.exists(self.__wc_id_attribute.get_meta().get_href(), True)

            for ms_product in MSApi.gen_products(filters=filters):
                try:
                    ms_product: Product
                    wc_id = ms_product.get_attribute_by_name(WC_ID_ATTR_NAME).get_value()

                    wc_product = WcApi.get("products/{}".format(wc_id))
                    wc_type = wc_product.get('type')
                    if wc_product.get('type') == 'variable':
                        if not ms_product.has_variants():
                            raise SyncroException("Change variant product to simple is not implemented now") # TODO change to simple
                        raise SyncroException("Unsupported product type: {}".format(wc_type)) # TODO sync variant
                    elif wc_type != 'simple':
                        raise SyncroException("Unsupported product type: {}".format(wc_type))
                    elif ms_product.has_variants():
                        raise SyncroException("Change simple product to variant is not implemented now") # TODO change to variant

                    wc_put_data = {}

                    wc_put_data |= self.__sync_name(ms_product, wc_product)
                    wc_put_data |= self.__sync_prices(ms_product, wc_product)

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

    def change_wooms_id_to_href(self):
        for wc_product in WcApi.gen_all_wc_products(cached=True):
            new_wc_meta_list = []
            wc_meta_list: [] = wc_product.get('meta_data')
            has_sync = False
            for meta_data in wc_meta_list:
                if meta_data.get('key') == "wooms_id":
                    ms_product = MSApi.get_product_by_id(meta_data.get('value'))
                    new_wc_meta_list.append({
                        'key': 'wooms_href',
                        'value': ms_product.get_meta().get_href()
                    })
                    new_wc_meta_list.append({
                        'key': 'wooms_id',
                        'value': None
                    })
                    has_sync = True
                else:
                    new_wc_meta_list.append(meta_data)
            if has_sync:
                WcApi.put(f'products/{wc_product.get("id")}', data={'meta_data': new_wc_meta_list})

    def __get_wc_put_data_prices(self, ms_object, wc_regular_price=None, wc_sale_price=None):
        """генерирует данные о ценах для Woocommerce на основе цен из моего склада"""
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


    def force_set_meta_by_name(self):
        for wc_product in WcApi.gen_all_wc_products(cached=True):
            wc_name = wc_product.get('name')
            ms_href = get_wooms_href(wc_product)
            if ms_href is not None:
                print(f"{wc_name}\t{ms_href}")
            else:
                ms_products = list(MSApi.gen_products(filters=Filter.eq('name', wc_name)))
                if len(ms_products) == 1:
                    wc_meta_list = wc_product.get('meta_data')
                    wc_meta_list.append({
                        'key': 'wooms_id',
                        'value': ms_products[0].get_id()
                    })
                    WcApi.put(f'products/{wc_product.get("id")}', data={'meta_data': wc_meta_list})
                    print(f"{wc_name}\tsuccess")
                elif len(ms_products) > 1:
                    print(f"{wc_name}\tmore one")
                else:
                    print(f"{wc_name}\tfail")

    def check_products_part_eq(self):
        from fuzzywuzzy import fuzz
        print("Loading MS products...")
        ms_products = []
        for ms_product in MSApi.gen_products():
            ms_products.append((ms_product.get_name(), ms_product.get_meta()))

        print("Loading WC products...")
        wc_products = []
        for wc_product in WcApi.gen_all_wc_products(cached=True):
            if get_wooms_href(wc_product) is None:
                wc_products.append((wc_product.get('name'), wc_product.get('id')))
        for wc_product in wc_products:
            for ms_product in ms_products:
                ratio = fuzz.ratio(ms_product[0], wc_product[0])
                if ratio < 80:
                    continue
                print(f"[ms] {ms_product[0]}\t-\t[wc] {wc_product[0]}")
                command = self.__input_command()
                if command == "q":
                    return
                if command == "s":
                    continue
                if command == "ms":
                    WcApi.put(f'products/{wc_product[1]}',
                              data={
                                  'meta_data': [
                                      {
                                          'key': 'wooms_href',
                                          'value': ms_product[1].get_href()
                                      }
                                  ]
                              })
                    print('Success!')
                    break
                if command == "wc":
                    try:
                        data = [{
                            'meta': ms_product[1],
                            'name': wc_product[0]
                        }]
                        MSApi.set_products(data)
                        print('Success!')
                    except MSApiException as e:
                        print(e)
                    break

    @staticmethod
    def __input_command():
        while True:
            command = input("? [q] - quit [s] - skip, [ms] - from moy_sklad, [wc] - from site: ")
            if command in ["q", "s", "ms", "wc"]:
                return command
            else:
                print("Wrong input")
