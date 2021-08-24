import configparser

from woocommerce import API

from MSApi.MSApi import MSApi, MSApiException, Filter

from requests.exceptions import ReadTimeout


class ProductsSyncro:

    def __init__(self, config_path):
        try:
            config = configparser.ConfigParser()
            config.read(config_path, encoding="utf-8")

            self.wcapi = API(
                url=config['woocommerce']['url'],
                consumer_key=config['woocommerce']['consumer_key'],
                consumer_secret=config['woocommerce']['consumer_secret'],
                version='wc/v3')

            MSApi.login(config['moy_sklad']['login'], config['moy_sklad']['password'])

        except MSApiException as e:
            print(e)
        except ReadTimeout as e:
            print(e)

    def force_set_meta_by_name(self):
        for wc_product in self.__gen_all_wc_products():
            wc_name = wc_product.get('name')
            ms_id = self.__get_wooms_meta(wc_product)
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
            if self.__get_wooms_meta(wc_product) is None:
                wc_products.append((wc_product.get('name'), wc_product.get('id')))
        for wc_product in wc_products:
            for ms_product in ms_products:
                ratio = fuzz.partial_ratio(ms_product[0], wc_product[0])
                if ratio < 90:
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

    @staticmethod
    def __get_wooms_meta(wc_product):
        wc_meta_list = wc_product.get('meta_data')
        for wc_meta in wc_meta_list:
            if wc_meta.get('key') != 'wooms_id':
                continue
            return wc_meta.get('value')
        else:
            return None
