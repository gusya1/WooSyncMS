import requests

from MSApi.Meta import Meta
from MSApi.Organization import Organization
from MSApi.Template import Template
from MSApi.Product import Product
from MSApi.Service import Service
from MSApi.ProductFolder import ProductFolder
from MSApi.Discount import Discount, SpecialPriceDiscount, AccumulationDiscount
from MSApi.PriceType import PriceType
from MSApi.CompanySettings import CompanySettings
from MSApi.properties import Filter, Search


class MSApiException(Exception):
    pass


class MSApiHttpException(MSApiException):
    def __init__(self, response):
        self.errors = []
        for json_error in response.json().get('errors'):
            self.errors.append(json_error.get('error'))
        self.status_code = response.status_code

    def __str__(self):
        return 'search={0}'.format("\n".join(self.errors))


class MSApi:
    __token = None
    __endpoint = "https://online.moysklad.ru/api/remap/1.2"

    __objects_dict = {
        'product': Product,
        'organization': Organization,
        'template': Template,
        'productfolder': ProductFolder,
        'discount': Discount,
        'specialpricediscount': SpecialPriceDiscount,
        'accumulationdiscount': AccumulationDiscount,
        'service': Service,
        'companysettings': CompanySettings
    }

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
    def get_company_settings(cls) -> CompanySettings:
        """Запрос на получение Настроек компании."""
        response = cls.__auch_get('context/companysettings')
        cls.__error_handler(response)
        return CompanySettings(response.json())

    @classmethod
    def get_default_price_type(cls) -> PriceType:
        """Получить тип цены по умолчанию"""
        response = cls.__auch_get('context/companysettings/pricetype/default')
        cls.__error_handler(response)
        return PriceType(response.json())

    @classmethod
    def get_object_by_meta(cls, meta: Meta):
        obj_type = cls.__objects_dict.get(meta.get_type())
        if obj_type is None:
            raise MSApiException(f"Unknown object type \"{meta.get_type()}\"")
        response = cls.__auch_get_by_href(meta.get_href())
        cls.__error_handler(response)
        return obj_type(response.json())

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
    def gen_productfolders(cls, **kwargs):
        response = cls.__auch_get('entity/productfolder', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield ProductFolder(row)

    @classmethod
    def gen_discounts(cls, **kwargs):
        response = cls.__auch_get('entity/discount', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield Discount(row)

    @classmethod
    def gen_special_price_discounts(cls, **kwargs):
        response = cls.__auch_get('entity/specialpricediscount', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield SpecialPriceDiscount(row)

    @classmethod
    def gen_accumulation_discounts(cls, **kwargs):
        response = cls.__auch_get('entity/accumulationdiscount', **kwargs)
        cls.__error_handler(response)
        for row in response.json().get('rows'):
            yield SpecialPriceDiscount(row)

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
            raise MSApiHttpException(response)

        return data

    @classmethod
    def __auch_post(cls, request, **kwargs):
        return requests.post(f"{cls.__endpoint}/{request}",
                             headers={"Authorization": f"Bearer {cls.__token}",
                                      "Content-Type": "application/json"},
                             **kwargs)

    @classmethod
    def __auch_get(cls, request, **kwargs):
        return cls.__auch_get_by_href(f"{cls.__endpoint}/{request}", **kwargs)

    @classmethod
    def __auch_get_by_href(cls, request, search: Search = None, filters: Filter = None, **kwargs):
        params = []
        if search is not None:
            params.append(str(search))
        if filters is not None:
            params.append(str(filters))
        params_str = ""
        if params:
            params_str = f"?{'&'.join(params)}"

        return requests.get(f"{request}{params_str}",
                            headers={"Authorization": f"Bearer {cls.__token}",
                                     "Content-Type": "application/json"},
                            **kwargs)

    @classmethod
    def __error_handler(cls, response: requests.Response, expected_code=200):
        code = response.status_code
        if code == expected_code:
            return
        raise MSApiHttpException(response)
