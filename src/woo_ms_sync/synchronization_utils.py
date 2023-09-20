from woo_commerce_models.product import Product

from woo_ms_sync.exceptions import MultiplyWooMsHrefError


def get_wooms_href(wc_product: Product):
    """"""
    wooms_href_list = list(meta.value for meta in wc_product.meta_data if meta.key == 'wooms_href')
    if wooms_href_list:
        if len(wooms_href_list) > 1:
            raise MultiplyWooMsHrefError()
        return wooms_href_list[0]
    return None
