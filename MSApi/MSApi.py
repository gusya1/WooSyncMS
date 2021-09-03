import requests

from MSApi.MSLowApi import MSLowApi, error_handler
from MSApi.exceptions import *

from MSApi.Meta import Meta
from MSApi.Organization import Organization
from MSApi.Template import Template
from MSApi.Product import Product
from MSApi.Service import Service
from MSApi.ProductFolder import ProductFolder
from MSApi.Discount import Discount, SpecialPriceDiscount, AccumulationDiscount
from MSApi.PriceType import PriceType
from MSApi.CompanySettings import CompanySettings
from MSApi.Bundle import Bundle
from MSApi.Variant import Variant


class MSApi(MSLowApi):

    __objects_dict = {
        'product': Product,
        'organization': Organization,
        'template': Template,
        'productfolder': ProductFolder,
        'discount': Discount,
        'specialpricediscount': SpecialPriceDiscount,
        'accumulationdiscount': AccumulationDiscount,
        'service': Service,
        'companysettings': CompanySettings,
        'bundle': Bundle,
        'variant': Variant
    }

    @classmethod
    def get_company_settings(cls) -> CompanySettings:
        """Запрос на получение Настроек компании."""
        response = cls.auch_get('context/companysettings')
        error_handler(response)
        return CompanySettings(response.json())

    @classmethod
    def get_default_price_type(cls) -> PriceType:
        """Получить тип цены по умолчанию"""
        response = cls.auch_get('context/companysettings/pricetype/default')
        error_handler(response)
        return PriceType(response.json())

    @classmethod
    def get_object_by_meta(cls, meta: Meta):
        obj_type = cls.__objects_dict.get(meta.get_type())
        if obj_type is None:
            raise MSApiException(f"Unknown object type \"{meta.get_type()}\"")
        response = cls._auch_get_by_href(meta.get_href())
        error_handler(response)
        return obj_type(response.json())

    @classmethod
    def get_object_by_json(cls, json_data):
        meta = Meta(json_data.get('meta'))
        obj_type = cls.__objects_dict.get(meta.get_type())
        if obj_type is None:
            raise MSApiException(f"Unknown object type \"{meta.get_type()}\"")
        return obj_type(json_data)

    @classmethod
    def get_object_by_href(cls, href):
        response = cls._auch_get_by_href(href)
        error_handler(response)
        return cls.get_object_by_json(response.json())

    @classmethod
    def gen_organizations(cls, **kwargs):
        response = cls.auch_get('entity/organization', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Organization(row)

    @classmethod
    def gen_variants(cls, **kwargs):
        response = cls.auch_get('entity/variant', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Variant(row)

    @classmethod
    def gen_services(cls, **kwargs):
        response = cls.auch_get('entity/service', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Service(row)

    @classmethod
    def gen_bundles(cls, **kwargs):
        response = cls.auch_get('entity/bundle', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Bundle(row)

    @classmethod
    def gen_assortment(cls, **kwargs):
        response = cls.auch_get('entity/assortment', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield cls.get_object_by_json(row)

    @classmethod
    def gen_customtemplates(cls, **kwargs):
        response = cls.auch_get('entity/assortment/metadata/customtemplate', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Template(row)

    @classmethod
    def gen_products(cls, **kwargs):
        response = cls.auch_get('entity/product', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Product(row)

    @classmethod
    def gen_productfolders(cls, **kwargs):
        response = cls.auch_get('entity/productfolder', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield ProductFolder(row)

    @classmethod
    def gen_discounts(cls, **kwargs):
        response = cls.auch_get('entity/discount', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield Discount(row)

    @classmethod
    def gen_special_price_discounts(cls, **kwargs):
        response = cls.auch_get('entity/specialpricediscount', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield SpecialPriceDiscount(row)

    @classmethod
    def gen_accumulation_discounts(cls, **kwargs):
        response = cls.auch_get('entity/accumulationdiscount', **kwargs)
        error_handler(response)
        for row in response.json().get('rows'):
            yield SpecialPriceDiscount(row)

    @classmethod
    def get_product_by_id(cls, product_id, **kwargs):
        response = cls.auch_get(f'entity/product/{product_id}', **kwargs)
        error_handler(response)
        return Product(response.json())

    @classmethod
    def set_products(cls, json_data):
        response = cls.__auch_post(f'entity/product/', json=json_data)
        error_handler(response)

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
