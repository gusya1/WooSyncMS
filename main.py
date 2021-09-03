import configparser

from ProductsSyncro import SyncroException

# from DiscountHandler import DiscountHandler
from Reporter import Reporter
from MSApi.MSApi import MSApi
from WcApi import WcApi, gen_all_wc_products

from NewAssortmentCreator import NewAssortmentCreator
from exceptions import *


def get_settings_list_parameter(parameter):
    result = []
    for param_elem in parameter.split('\n'):
        if not param_elem:
            continue
        result.append(param_elem)
    return result


if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read("settings.ini", encoding="utf-8")

        WcApi.login(
            url=config['woocommerce']['url'],
            consumer_key=config['woocommerce']['consumer_key'],
            consumer_secret=config['woocommerce']['consumer_secret'])
        WcApi.read_only_mode = True

        MSApi.login(config['moy_sklad']['login'], config['moy_sklad']['password'])
        sale_group_tag = config['moy_sklad']['group_tag']

        wc_products = list(gen_all_wc_products())

        assortment_creator = NewAssortmentCreator(wc_products, sale_group_tag)
        assortment_creator.set_productfolder_ids_blacklist(
            get_settings_list_parameter(config['moy_sklad']['groups_blacklist']))
        assortment_creator.set_assortment_ids_blacklist(
            get_settings_list_parameter(config['moy_sklad']['assortment_blacklist']))

        assortment_creator.create_new_wc_products()

        print(Reporter.to_str())

    except KeyError as e:
        print(e)
    except SyncroException as e:
        print(e)
    except WcApiException as e:
        print(e)
    except ReporterException as e:
        print(e)
