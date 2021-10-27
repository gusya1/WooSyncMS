import configparser

from MSApi.MSApi import MSApi, MSApiException
from WcApi import WcApi


from NewAssortmentCreator import NewAssortmentCreator
from exceptions import *


def input_command():
    command = input("Product ID?")
    return command


if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read("settings.ini", encoding="utf-8")

        WcApi.login(
            url=config['woocommerce']['url'],
            consumer_key=config['woocommerce']['consumer_key'],
            consumer_secret=config['woocommerce']['consumer_secret'])
        WcApi.read_only_mode = True

        MSApi.set_access_token(config['moy_sklad']['access_token'])
        sale_group_tag = config['moy_sklad']['group_tag']

        wc_products = list(WcApi.gen_all_wc_products())
        assortment_creator = NewAssortmentCreator(wc_products, sale_group_tag)

        while True:
            try:
                ms_id = input("Product ID?")
                wc_product_id = assortment_creator.create_new_product(ms_id)
                print(wc_product_id)
            except CheckAssortmentException as e:
                print(e)
            except SyncroException as e:
                print(e)
            except WcApiException as e:
                print(e)
            except MSApiException as e:
                print(str(e))
    except ReporterException as e:
        print(e)
    except KeyError as e:
        print(e)
