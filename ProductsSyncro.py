from MSApi.MSApi import MSApi, MSApiException, MSApiHttpException, Product, Service, Bundle, Variant
from MSApi.properties import *
from requests.exceptions import RequestException, ConnectTimeout
from DiscountHandler import DiscountHandler
from Reporter import Reporter
from WcApi import WcApi, get_wooms_href
from exceptions import SyncroException


class ProductsSyncro:

    def __init__(self, wc_products, sale_group_tag):
        self.__wc_products = wc_products
        self.__sale_group_tag = sale_group_tag

    def find_duplicate_wc_products(self):
        """ищет повторяющиеся продукты"""
        Reporter.add_report_group('duples', "WooCommerce products duplicates")
        ignore_ids = []
        for wc_product_1 in self.__wc_products:
            wooms_href_1 = get_wooms_href(wc_product_1)
            if wooms_href_1 is None:
                continue
            wc_product_id_1 = wc_product_1.get('id')
            if wc_product_id_1 in ignore_ids:
                continue
            duplicates = []
            for wc_product_2 in self.__wc_products:
                wc_product_id_2 = wc_product_2.get('id')
                if wc_product_id_1 == wc_product_id_2:
                    continue
                wooms_href_2 = get_wooms_href(wc_product_2)
                if wooms_href_1 == wooms_href_2:
                    duplicates.append(f"{wc_product_2.get('name')} ({wc_product_id_2})")
                    ignore_ids.append(wc_product_id_2)
            if duplicates:
                Reporter.append_report('duples', "Product \"{0} ({1})\" duplicates:\n{2}".format(
                    wc_product_1.get('name'),
                    wc_product_id_1,
                    "\n\t".join(duplicates)))

    def sync_products(self):
        try:
            Reporter.add_report_group('unsync', "Unsyncronized WooCommerce products")
            Reporter.add_report_group('changes', "Changed products")
            Reporter.add_report_group('errors', "Errors")
            for wc_product in self.__wc_products:
                wooms_href = get_wooms_href(wc_product)
                if wooms_href is None:
                    Reporter.append_report('unsync', wc_product.get('name'))
                    continue
                try:
                    wc_regular_price, wc_sale_price = self.__get_wc_prices(wc_product)
                    change_wc_product_report = []
                    wc_put_data = {}

                    ms_object = MSApi.get_object_by_href(wooms_href)
                    if type(ms_object) in [Product, Service, Bundle]:
                        if type(ms_object) == Product:
                            if ms_object.get_variants_count() != 1:
                                wc_put_data['meta_data'] = {
                                    'key': 'wooms_variants',
                                    'value': ''
                                }

                        wc_put_data |= self.__get_wc_put_data_prices(ms_object, wc_regular_price, wc_sale_price)
                        ms_regular_price = wc_put_data.get('regular_price')
                        if ms_regular_price is not None:
                            change_wc_product_report.append(
                                f"\tRegular price changed from {wc_regular_price} to {ms_regular_price}")

                        ms_sale_price = wc_put_data.get('sale_price')
                        if ms_sale_price is not None:
                            change_wc_product_report.append(
                                f"\tSale price changed from {wc_sale_price} to {ms_sale_price}")

                        ms_name = ms_object.get_name()
                        wc_name = wc_product.get('name')
                        if ms_name != wc_name:
                            wc_put_data['name'] = ms_name
                            change_wc_product_report.append(
                                f"\tName changed from \"{wc_name}\" to \"{ms_name}\"")

                    elif type(ms_object) == Variant:
                        pass
                    else:
                        raise SyncroException("Unexpected object type")
                    if wc_put_data:
                        WcApi.put(f'products/{wc_product.get("id")}', data=wc_put_data)
                except MSApiHttpException as e:
                    Reporter.append_report('errors', str(e))
                except SyncroException as e:
                    Reporter.append_report('errors', str(e))
                except RequestException as e:
                    Reporter.append_report('errors', str(e))
                else:
                    if change_wc_product_report:
                        Reporter.append_report('changes', "Product \"{0}\" changed:\n{1}".format(
                            ms_object.get_name(),
                            '\n'.join(change_wc_product_report)))
        except ConnectTimeout as e:
            Reporter.append_report('errors', str(e))

    @staticmethod
    def attach_wc_product(ms_href, wc_id):
        wc_product = WcApi.get(f'products/{wc_id}')
        if get_wooms_href(wc_product) is not None:
            raise SyncroException("Wc product {} is busy".format(wc_id))
        WcApi.put(f'products/{wc_product.get("id")}', data={'meta_data': [{
            'key': 'wooms_href',
            'value': ms_href
        }]})

    @staticmethod
    def detach_wc_product(wc_id):
        wc_product = WcApi.get(f'products/{wc_id}')
        if get_wooms_href(wc_product) is None:
            raise SyncroException("Wc product {} not attached".format(wc_id))
        WcApi.put(f'products/{wc_product.get("id")}', data={'meta_data': [{
            'key': 'wooms_href',
            'value': None
        }]})

    def change_wooms_id_to_href(self):
        for wc_product in self.__wc_products:
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

    @staticmethod
    def __get_wc_prices(wc_product):
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

    def force_set_meta_by_name(self):
        for wc_product in self.__wc_products:
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
        for wc_product in self.__wc_products:
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
