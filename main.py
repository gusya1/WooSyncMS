import configparser
import os
import sys

from MSApi.MSApi import MSApi, MSApiException, MSApiHttpException
from WcApi import WcApi

from CustomerOrderSyncro import CustomerOrderSyncro
from ProductsSyncro import ProductsSyncro
from exceptions import *
import logging


def get_settings_list_parameter(parameter):
    result = []
    for param_elem in parameter.split('\n'):
        if not param_elem:
            continue
        result.append(param_elem)
    return result


if __name__ == '__main__':
    try:
        log_format = '[%(levelname)s] - %(message)s'
        logging.basicConfig(level=logging.INFO, format=log_format)

        config = configparser.ConfigParser()
        config.read(os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.ini"), encoding="utf-8")

        WcApi.login(
            url=config['woocommerce']['url'],
            consumer_key=config['woocommerce']['consumer_key'],
            consumer_secret=config['woocommerce']['consumer_secret'])
        WcApi.read_only_mode = False

        MSApi.set_access_token(config['moy_sklad']['access_token'])
        sale_group_tag = config['moy_sklad']['group_tag']

        start_product_syncro = (len(sys.argv) == 1) or ('--products' in sys.argv)

        if '--orders' in sys.argv:
            logging.info("Starting CustomerOrder syncro...")
            order_sync = CustomerOrderSyncro(sale_group_tag)
            order_sync.check_and_correct_ms_phone_numbers()
            start_product_syncro = start_product_syncro or order_sync.sync_orders()
            logging.info("CustomerOrder syncro completed")

        if start_product_syncro:
            logging.info("Starting Assortment syncro...")
            products_sync = ProductsSyncro(sale_group_tag)
            products_sync.find_duplicate_wc_products()
            products_sync.find_unsync_wc_products()
            products_sync.create_new_characteristics()
            products_sync.create_new_bundles()
            products_sync.sync_products()
            products_sync.sync_bundles()
            products_sync.create_new_products()
            logging.info("Assortment syncro completed")

    except KeyError as e:
        print(e)
    except SyncroException as e:
        print(e)
    except WcApiException as e:
        print("WooCommerce error: \'{}\'".format(e))
    except MSApiHttpException as e:
        print(e)
    except ReporterException as e:
        print(e)
