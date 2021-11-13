from woocommerce import API
from exceptions import WcApiException
from MSApi import caching


class WcApi:
    wcapi = None
    read_only_mode = False

    @classmethod
    def login(cls, url, consumer_key, consumer_secret):
        cls.wcapi = API(
            url=url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            version='wc/v3')

    @classmethod
    def get(cls, endpoint, **kwargs):
        response = cls.wcapi.get(endpoint, **kwargs)
        cls.__check_error(response)
        return response.json()

    @classmethod
    def put(cls, endpoint, data, **kwargs):
        if cls.read_only_mode:
            return None
        response = cls.wcapi.put(endpoint, data, **kwargs)
        cls.__check_error(response)
        return response.json()

    @classmethod
    def post(cls, endpoint, data, **kwargs):
        if cls.read_only_mode:
            return None
        response = cls.wcapi.post(endpoint, data, **kwargs)
        cls.__check_error(response)
        return response.json()

    @staticmethod
    def __check_error(response):
        if response.status_code not in [200, 201]:
            if response.status_code in [503, 500]:
                raise WcApiException(str(response.reason))
            raise WcApiException(response.json().get('message'))

    @classmethod
    @caching
    def gen_all_wc(cls, entity, filters: {str: str} = None, **kwargs):
        page_iterator = 1
        filters_str = ""
        if filters is not None:
            for filter_parameter, filter_value in filters.items():
                filters_str += f"&{filter_parameter}={filter_value}"

        while True:
            wc_product_list = cls.get(f'{entity}?per_page=50&page={page_iterator}{filters_str}', **kwargs)
            if len(wc_product_list) == 0:
                break
            for wc_product in wc_product_list:
                yield wc_product
            page_iterator += 1

    @classmethod
    @caching
    def gen_all_wc_products(cls, **kwargs):
        return cls.gen_all_wc(entity="products", **kwargs)


def gen_all_wc_variations(wc_product_id):
    page_iterator = 1
    while True:
        wc_product_list = WcApi.get(f'products/{wc_product_id}/variations?per_page=50&page={page_iterator}')
        if len(wc_product_list) == 0:
            break
        for wc_product in wc_product_list:
            yield wc_product
        page_iterator += 1

def get_wooms_href(wc_product):
    wc_meta_list = wc_product.get('meta_data')
    for wc_meta in wc_meta_list:
        if wc_meta.get('key') != 'wooms_href':
            continue
        return wc_meta.get('value')
    else:
        return None

