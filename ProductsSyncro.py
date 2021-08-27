import configparser

from typing import Union

from woocommerce import API
from MSApi.MSApi import MSApi, MSApiException, MSApiHttpException, Filter, Product, PriceType
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
            # "Unsyncronized WooCommerce products: \n{0}\n\nChanged products:\n{1}\n\nErrors:\n{2}".format(
            # '\n\t'.join(name.get('name') for name in self.unsynchronized_wc_products),
            # '\n'.join(('\n\t'.join(message.split('\n'))) for message in self.changed_products),
            # '\n\t'.join(self.errors))

    @staticmethod
    def __group_to_str(group: (str, [str])) -> str:
        result = "{display_name}: \n\t{reports}".format(
            display_name=group[0],
            reports='\n\t'.join(('\n\t\t'.join(report.split('\n'))) for report in group[1]))
        return result


class ProductsSyncro:
    def __init__(self, config_path):
        try:
            config = configparser.ConfigParser()
            config.read(config_path, encoding="utf-8")

            self.report = SyncReport()

            self.wcapi = API(
                url=config['woocommerce']['url'],
                consumer_key=config['woocommerce']['consumer_key'],
                consumer_secret=config['woocommerce']['consumer_secret'],
                version='wc/v3')

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
            wooms_id_1 = self.__get_wooms_id(wc_product_1)
            wc_product_id_1 = wc_product_1.get('id')
            if wc_product_id_1 in ignore_ids:
                continue
            if wooms_id_1 is None:
                continue
            duplicates = []
            for wc_product_2 in self.__wc_products:
                wc_product_id_2 = wc_product_2.get('id')
                if wc_product_id_1 == wc_product_id_2:
                    continue
                wooms_id_2 = self.__get_wooms_id(wc_product_2)
                if wooms_id_1 == wooms_id_2:
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
                wooms_id = self.__get_wooms_id(wc_product)
                if wooms_id is None:
                    self.report.append_report('unsync', wc_product.get('name'))
                    continue
                try:
                    ms_product = MSApi.get_product_by_id(wooms_id)
                    ms_regular_price = self.discount_handler.get_default_price_value(ms_product)
                    ms_sale_price = self.discount_handler.get_actual_price(ms_product, self.__sale_group_tag)
                    wc_regular_price, wc_sale_price = self.__get_wc_prices(wc_product)

                    change_wc_product_report = []
                    wc_put_data = {}
                    if ms_regular_price != wc_regular_price:
                        wc_put_data['regular_price'] = str(ms_regular_price)
                        change_wc_product_report.append(
                            f"\tRegular price changed from {wc_regular_price} to {ms_regular_price}")

                    if ms_sale_price == ms_regular_price:
                        ms_sale_price = None

                    if ms_sale_price != wc_sale_price:
                        if ms_sale_price is None:
                            wc_put_data['sale_price'] = ''
                        else:
                            wc_put_data['sale_price'] = str(ms_sale_price)
                        change_wc_product_report.append(
                            f"\tSale price changed from {wc_sale_price} to {ms_sale_price}")

                    ms_name = ms_product.get_name()
                    wc_name = wc_product.get('name')
                    if ms_name != wc_name:
                        wc_put_data['name'] = ms_product.get_name()
                        change_wc_product_report.append(
                            f"\tName changed from \"{wc_name}\" to \"{ms_name}\"")
                    #
                    # if wc_put_data:
                    #     response = self.wcapi.put(f'products/{wc_product.get("id")}', data=wc_put_data)
                    #     if response.status_code != 200:
                    #         raise SyncroException(response.json())

                except MSApiHttpException as e:
                    self.report.append_report('errors', str(e))
                except SyncroException as e:
                    self.report.append_report('errors', str(e))
                except RequestException as e:
                    self.report.append_report('errors', str(e))
                else:
                    if change_wc_product_report:
                        self.report.append_report('changes', "Product \"{0}\" changed:\n{1}".format(
                            ms_product.get_name(),
                            '\n'.join(change_wc_product_report)))
        except ConnectTimeout as e:
            self.report.append_report('errors', str(e))

    def create_new_wc_products(self):
        wooms_ids = []
        for wc_product in self.__wc_products:
            wooms_id = self.__get_wooms_id(wc_product)
            if wooms_id is None:
                continue
            wooms_ids.append(wooms_id)

        productfolder_filter = Filter()
        for productfolder_id in self.__productfolder_ids_blacklist:
            productfolder_filter += Filter.ne('productFolder', productfolder_id)

        for ms_product in MSApi.gen_products(filters=productfolder_filter):
            if ms_product.get_id() in wooms_ids:
                continue
            print(ms_product)


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
            ms_id = self.__get_wooms_id(wc_product)
            if ms_id is not None:
                print(f"{wc_name}\t{ms_id}")
            else:
                ms_products = list(MSApi.gen_products(filters=Filter.eq('name', wc_name)))
                if len(ms_products) == 1:
                    wc_meta_list = wc_product.get('meta_data')
                    wc_meta_list.append({
                        'key': 'wooms_id',
                        'value': ms_products[0].get_id()
                    })
                    response = self.wcapi.put(f'products/{wc_product.get("id")}',
                                              data={'meta_data': wc_meta_list})
                    print(f"{wc_name}\tsuccess")
                    if response.status_code != 200:
                        raise Exception(response.json())
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
            if self.__get_wooms_id(wc_product) is None:
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
                    response = self.wcapi.put(f'products/{wc_product[1]}',
                                              data={'name': ms_product[0]})
                    if response.status_code != 200:
                        print(response.json())
                    else:
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
    #
    # def sync_actual_descriptions_from_wc(self):
    #     """"""
    #     update_data = []
    #     for wc_product in self.__gen_all_wc_products():
    #         wooms_id = self.__get_wooms_id(wc_product)
    #         if wooms_id is None:
    #             continue
    #         ms_product = MSApi.get_product_by_id(wooms_id)
    #         wc_desc = wc_product.get('description')
    #         ms_desc = ms_product.get_description() or ""
    #         if not ms_desc:
    #             update_data.append({
    #                 'meta': ms_product.get_meta(),
    #                 'description': wc_desc
    #             })
    #     MSApi.set_products(update_data)

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
            response = self.wcapi.get(f'products?per_page=100&page={page_iterator}')
            wc_product_list = response.json()
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
    def __get_wooms_id(wc_product):
        wc_meta_list = wc_product.get('meta_data')
        for wc_meta in wc_meta_list:
            if wc_meta.get('key') != 'wooms_id':
                continue
            return wc_meta.get('value')
        else:
            return None
