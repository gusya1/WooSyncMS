import configparser
from typing import Union
from woocommerce import API
from MSApi.MSApi import MSApi, MSApiException, MSApiHttpException, Filter, Product, Service, Bundle, Variant, Expand
from MSApi.Variant import Characteristic
from requests.exceptions import RequestException, ConnectTimeout
from DiscountHandler import DiscountHandler


class SyncroException(Exception):
    pass


class SyncReport:

    def __init__(self):
        self.__report_groups: {str: (str, [str])} = {}

    def add_report_group(self, group_name: str, display_name: str):
        self.__report_groups[group_name] = (display_name, [])

    def append_report(self, group_name: str, report: str):
        self.__report_groups[group_name][1].append(report)

    def __str__(self):
        result = "\n\n".join(self.__group_to_str(group) for group in self.__report_groups.values())
        return result

    @staticmethod
    def __group_to_str(group: (str, [str])) -> str:
        result = "{display_name}: \n\t{reports}".format(
            display_name=group[0],
            reports='\n\t'.join(('\n\t\t'.join(report.split('\n'))) for report in group[1]))
        return result


class WcApi:
    def __init__(self, url, consumer_key, consumer_secret, read_only_mode=False):
        self.wcapi = API(
            url=url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            version='wc/v3')
        self.read_only_mode = read_only_mode

    def get(self, endpoint, **kwargs):
        response = self.wcapi.get(endpoint, **kwargs)
        self.__check_error(response)
        return response.json()

    def put(self, endpoint, data, **kwargs):
        if self.read_only_mode:
            return None
        response = self.wcapi.put(endpoint, data, **kwargs)
        self.__check_error(response)
        return response.json()

    def post(self, endpoint, data, **kwargs):
        if self.read_only_mode:
            return None
        response = self.wcapi.post(endpoint, data, **kwargs)
        self.__check_error(response)
        return response.json()

    @staticmethod
    def __check_error(response):
        if response.status_code != 200:
            raise SyncroException(response.json().get('message'))


class ProductsSyncro:
    def __init__(self, config_path, read_only_mode=False):
        try:
            config = configparser.ConfigParser()
            config.read(config_path, encoding="utf-8")

            self.report = SyncReport()

            self.wcapi = WcApi(
                url=config['woocommerce']['url'],
                consumer_key=config['woocommerce']['consumer_key'],
                consumer_secret=config['woocommerce']['consumer_secret'],
                read_only_mode=read_only_mode)

            MSApi.login(config['moy_sklad']['login'], config['moy_sklad']['password'])
            self.discount_handler = DiscountHandler()

            self.__sale_group_tag = config['moy_sklad']['group_tag']
            self.__productfolder_ids_blacklist = []
            for productfolder_id in config['moy_sklad']['groups_blacklist'].split('\n'):
                if not productfolder_id:
                    continue
                self.__productfolder_ids_blacklist.append(productfolder_id)

            self.__wc_products = list(self.__gen_all_wc_products())

        except KeyError as e:
            print(e)
        except MSApiException as e:
            print(e)
        except RequestException as e:
            print(e)

    def find_duplicate_wc_products(self):
        """ищет повторяющиеся продукты"""
        self.report.add_report_group('duples', "WooCommerce products duplicates")
        ignore_ids = []
        for wc_product_1 in self.__wc_products:
            wooms_href_1 = self.__get_wooms_href(wc_product_1)
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
                wooms_href_2 = self.__get_wooms_href(wc_product_2)
                if wooms_href_1 == wooms_href_2:
                    duplicates.append(f"{wc_product_2.get('name')} ({wc_product_id_2})")
                    ignore_ids.append(wc_product_id_2)
            if duplicates:
                self.report.append_report('duples', "Product \"{0} ({1})\" duplicates:\n{2}".format(
                    wc_product_1.get('name'),
                    wc_product_id_1,
                    "\n\t".join(duplicates)))

    def sync_products(self):
        try:
            self.report.add_report_group('unsync', "Unsyncronized WooCommerce products")
            self.report.add_report_group('changes', "Changed products")
            self.report.add_report_group('errors', "Errors")
            for wc_product in self.__wc_products:
                wooms_href = self.__get_wooms_href(wc_product)
                if wooms_href is None:
                    self.report.append_report('unsync', wc_product.get('name'))
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
                        self.wcapi.put(f'products/{wc_product.get("id")}', data=wc_put_data)
                except MSApiHttpException as e:
                    self.report.append_report('errors', str(e))
                except SyncroException as e:
                    self.report.append_report('errors', str(e))
                except RequestException as e:
                    self.report.append_report('errors', str(e))
                else:
                    if change_wc_product_report:
                        self.report.append_report('changes', "Product \"{0}\" changed:\n{1}".format(
                            ms_object.get_name(),
                            '\n'.join(change_wc_product_report)))
        except ConnectTimeout as e:
            self.report.append_report('errors', str(e))

    def create_new_wc_products(self):
        sync_wc_products = {}
        for wc_product in self.__wc_products:
            product_wooms_href = self.__get_wooms_href(wc_product)
            if product_wooms_href is not None:
                sync_wc_products[product_wooms_href] = wc_product.get('id')
            if wc_product.get('type') == 'variable':
                for wc_variation in self.__gen_all_wc_variations(wc_product.get('id')):
                    variation_wooms_href = self.__get_wooms_href(wc_variation)
                    if variation_wooms_href is not None:
                        sync_wc_products[variation_wooms_href] = wc_variation.get('id')

        self.report.add_report_group('new_variants', "New variants created")
        self.report.add_report_group('new_products', "New products created")

        self.__create_new_wc_variants(sync_wc_products)
        self.__create_new_wc_products(sync_wc_products.values())
        self.__create_new_wc_services(sync_wc_products.values())
        self.__create_new_wc_bundles(sync_wc_products.values())

    def __create_new_wc_variants(self, sync_wc_products_href: {str: str}):
        for ms_variation in MSApi.gen_variants():
            if ms_variation.get_meta().get_href() not in sync_wc_products_href.keys():
                continue
            # все модификации, которых нет на сайте
            wc_product_id = sync_wc_products_href.get(ms_variation.get_product().get_meta().get_href())
            if wc_product_id is None:
                continue
            # все модификации, которых нет на сайте, но чей родитель есть
            response = self.wcapi.get(f'products/{wc_product_id}')
            self.__create_wc_variant(ms_variation, response)

    def __create_new_wc_products(self, sync_wc_products_ids: [str]):
        for ms_product in MSApi.gen_products(expand=Expand('productFolder')):
            if ms_product.get_meta().get_href() in sync_wc_products_ids:
                continue
            productfolder = ms_product.get_productfolder()
            if productfolder is None:
                continue  # TODO что делать с товарами без группы
            if ms_product.get_productfolder().get_id() in self.__productfolder_ids_blacklist:
                continue

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

            response = self.wcapi.post('products', wc_put_data)
            self.report.append_report('new_products', '"{}"'.format(ms_product.get_name()))
            if response is not None:
                wc_product_id = response.get('id')
                if ms_product.has_variants():
                    self.__create_new_wc_variations(wc_product_id, ms_product.get_id())

    def __create_new_wc_services(self, sync_wc_products_ids: [str]):
        for ms_service in MSApi.gen_services(expand=Expand('productFolder')):
            if ms_service.get_meta().get_href() in sync_wc_products_ids:
                continue
            productfolder = ms_service.get_productfolder()
            if productfolder is None:
                continue  # TODO что делать с товарами без группы
            if ms_service.get_productfolder().get_id() in self.__productfolder_ids_blacklist:
                continue

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

            self.wcapi.post('products', wc_put_data)
            self.report.append_report('new_products', '"{}"'.format(ms_service.get_name()))

    def __create_new_wc_bundles(self, sync_wc_products_href: [str]):
        for ms_bundle in MSApi.gen_bundles(expand=Expand('productFolder')):
            if ms_bundle.get_meta().get_href() in sync_wc_products_href:
                continue
            productfolder = ms_bundle.get_productfolder()
            if productfolder is None:
                continue  # TODO что делать с товарами без группы
            if ms_bundle.get_productfolder().get_id() in self.__productfolder_ids_blacklist:
                continue

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

            self.wcapi.post('products', wc_put_data)
            self.report.append_report('new_products', '"{}"'.format(ms_bundle.get_name()))

    def __create_new_wc_variations(self, wc_product_id, ms_product_id):
        all_characteristics: {str: [Characteristic]} = {}
        for ms_variant in MSApi.gen_variants(filters=Filter.eq('productid', ms_product_id)):
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
        wc_product = self.wcapi.put(f'products/{wc_product_id}', wc_put_data)

        for ms_variant in MSApi.gen_variants(filters=Filter.eq('productid', ms_product_id)):
            self.__create_wc_variant(ms_variant, wc_product)

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
        self.wcapi.put(f'products/{wc_product.get(id)}/variations', wc_variant_put_data)
        self.report.append_report('new_variants', 'In product "{}" with attributes:\n{}'.format(
            ms_variant.get_name(),
            "\n\t".join(report_attributes_strings)))

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
                self.wcapi.put(f'products/{wc_product.get("id")}', data={'meta_data': new_wc_meta_list})

    def __get_wc_put_data_prices(self, ms_object, wc_regular_price=None, wc_sale_price=None):
        wc_put_data = {}
        ms_regular_price = self.discount_handler.get_default_price_value(ms_object)
        ms_sale_price = self.discount_handler.get_actual_price(ms_object, self.__sale_group_tag)
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
        for wc_product in self.__gen_all_wc_products():
            wc_name = wc_product.get('name')
            ms_href = self.__get_wooms_href(wc_product)
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
                    self.wcapi.put(f'products/{wc_product.get("id")}', data={'meta_data': wc_meta_list})
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
        for wc_product in self.__gen_all_wc_products():
            if self.__get_wooms_href(wc_product) is None:
                wc_products.append((wc_product.get('name'), wc_product.get('id')))
        for wc_product in wc_products:
            for ms_product in ms_products:
                ratio = fuzz.partial_ratio(ms_product[0], wc_product[0])
                if ratio < 80:
                    continue
                print(f"[ms] {ms_product[0]}\t-\t[wc] {wc_product[0]}")
                command = self.__input_command()
                if command == "q":
                    return
                if command == "s":
                    continue
                if command == "ms":
                    self.wcapi.put(f'products/{wc_product[1]}', data={'name': ms_product[0]})
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

    def __gen_all_wc_products(self):
        page_iterator = 1
        while True:
            wc_product_list = self.wcapi.get(f'products?per_page=100&page={page_iterator}')
            if len(wc_product_list) == 0:
                break
            for wc_product in wc_product_list:
                yield wc_product
            page_iterator += 1

    def __gen_all_wc_variations(self, wc_product_id):
        page_iterator = 1
        while True:
            wc_product_list = self.wcapi.get(f'products/{wc_product_id}/variations?per_page=100&page={page_iterator}')
            if len(wc_product_list) == 0:
                break
            for wc_product in wc_product_list:
                yield wc_product
            page_iterator += 1

    def __gen_all_wc_categories(self):
        page_iterator = 1
        while True:
            response = self.wcapi.get(f'products/categories?per_page=100&page={page_iterator}')
            wc_category_list = response.json()
            if len(wc_category_list) == 0:
                break
            for wc_category in wc_category_list:
                yield wc_category
            page_iterator += 1

    @staticmethod
    def __get_wooms_href(wc_product):
        wc_meta_list = wc_product.get('meta_data')
        for wc_meta in wc_meta_list:
            if wc_meta.get('key') != 'wooms_href':
                continue
            return wc_meta.get('value')
        else:
            return None
