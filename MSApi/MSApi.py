import requests

from MSApi.Organization import Organization
from MSApi.Template import Template
from MSApi.Product import Product


class MSApiException(Exception):
    pass


class Search:

    def __init__(self, *args):
        self.search_list = []
        for arg in args:
            self.search_list.append(str(arg))

    def __str__(self):
        return f"search={' '.join(self.search_list)}"


class Filter(object):

    @classmethod
    def eq(cls, parameter, data):
        return Filter("=", parameter, data)

    @classmethod
    def mr(cls, parameter, data):
        return Filter(">", parameter, data)

    @classmethod
    def ls(cls, parameter, data):
        return Filter("<", parameter, data)

    @classmethod
    def me(cls, parameter, data):
        return Filter(">=", parameter, data)

    @classmethod
    def le(cls, parameter, data):
        return Filter("<=", parameter, data)

    @classmethod
    def ne(cls, parameter, data):
        return Filter("!=", parameter, data)

    @classmethod
    def siml(cls, parameter, data):
        return Filter("~=", parameter, data)

    @classmethod
    def simr(cls, parameter, data):
        return Filter("=~", parameter, data)

    @classmethod
    def sim(cls, parameter, data):
        return Filter("~", parameter, data)

        # ['=', '>', '<', '>=', '<=', '!=', '~', '~=', '=~']

    def __init__(self, operator, parameter, data):
        self.filters = [f"{parameter}{operator}{data}"]

    def __str__(self):
        return f"filter={';'.join(self.filters)}"

    def __add__(self, other):
        self.filters.append(other.filters)


class MSApi:
    __token = None
    __endpoint = "https://online.moysklad.ru/api/remap/1.2"

    def __init__(self):
        pass

    @classmethod
    def login(cls, login: str, password: str):
        import base64
        auch_base64 = base64.b64encode(f"{login}:{password}".encode('utf-8')).decode('utf-8')
        response = requests.post(f"{cls.__endpoint}/security/token",
                                 headers={"Authorization": f"Basic {auch_base64}"})
        cls.__error_handler(response, 201)
        cls.__token = str(response.json()["access_token"])

    @classmethod
    def gen_organizations(cls, **kwargs):
        response = cls.__auch_get('entity/organization', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield Organization(row)

    @classmethod
    def gen_customtemplates(cls, **kwargs):
        response = cls.__auch_get('entity/assortment/metadata/customtemplate', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield Template(row)

    @classmethod
    def gen_products(cls, **kwargs):
        response = cls.__auch_get('entity/product', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield Product(row)

    @classmethod
    def get_product_by_id(cls, product_id, **kwargs):
        response = cls.__auch_get(f'entity/product/{product_id}', **kwargs)
        cls.__error_handler(response)
        return Product(response.json())

    @classmethod
    def set_products(cls, json_data):
        response = cls.__auch_post(f'entity/product/', json=json_data)
        cls.__error_handler(response)

    @classmethod
    def load_label(cls, product: Product, organization: Organization, template: Template, sale_price=None):

        if not sale_price:
            sale_price = next(product.gen_sale_prices(), None)
            if not sale_price:
                raise MSApiException(f"Sale prices is empty in {product}")

        request_json = {
            'organization': {
                'meta': organization.get_meta()
            },
            'count': 1,
            'salePrice': sale_price.get_json(),
            'template': {
                'meta': template.get_meta()
            }

        }

        response = cls.__auch_post(f"/entity/product/{product.get_id()}/export", json=request_json)

        if response.status_code == 303:
            url = response.json().get('Location')
            file_response = requests.get(url)
            data = file_response.content
        elif response.status_code == 200:
            data = response.content
        else:
            raise MSApiException(response.json().get('errors')[0].get('error'))

        return data

    @classmethod
    def __auch_post(cls, request, **kwargs):
        return requests.post(f"{cls.__endpoint}/{request}",
                             headers={"Authorization": f"Bearer {cls.__token}",
                                      "Content-Type": "application/json"},
                             **kwargs)

    @classmethod
    def __auch_get(cls, request, search: Search = None, filters: Filter = None, **kwargs):
        params = []
        if search is not None:
            params.append(str(search))
        if filters is not None:
            params.append(str(filters))
        params_str = ""
        if params:
            params_str = f"?{'&'.join(params)}"

        return requests.get(f"{cls.__endpoint}/{request}{params_str}",
                            headers={"Authorization": f"Bearer {cls.__token}",
                                     "Content-Type": "application/json"},
                            **kwargs)

    @classmethod
    def __error_handler(cls, response: requests.Response, expected_code=200):
        code = response.status_code
        if code == expected_code:
            return
        raise MSApiException(response.json().get('errors')[0].get('error'))
