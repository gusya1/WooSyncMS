import unittest

from woo_commerce_models.product import Product, ProductMetaData, ProductType

from woo_ms_sync.synchronization_utils import get_wooms_href
from woo_ms_sync.exceptions import MultiplyWooMsHrefError


def _get_default_product():
    return Product(
        id=0,
        type=ProductType.SIMPLE,
        meta_data=[]
    )


class GetWooMsHrefTests(unittest.TestCase):

    def test_without_wooms_href(self):
        product = _get_default_product()

        result = get_wooms_href(product)
        self.assertIsNone(result)

    def test_with_wooms_href(self):
        product = _get_default_product()
        product.meta_data = [
            ProductMetaData(id=1, key="wooms_href", value="result")
        ]
        result = get_wooms_href(product)
        self.assertEqual(result, "result")

    def test_with_multiply_wooms_href(self):
        product = _get_default_product()
        product.meta_data = [
            ProductMetaData(id=1, key="wooms_href", value="result1"),
            ProductMetaData(id=2, key="wooms_href", value="result2")
        ]
        with self.assertRaises(MultiplyWooMsHrefError):
            get_wooms_href(product)