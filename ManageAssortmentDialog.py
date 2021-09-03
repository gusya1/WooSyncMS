import configparser

from MSApi.MSApi import MSApi, MSApiException
from WcApi import WcApi, gen_all_wc_products

from NewAssortmentCreator import NewAssortmentCreator
from ProductsSyncro import ProductsSyncro
from exceptions import *
from DialogManager import DialogManager

import json

if __name__ == '__main__':
    try:
        config = configparser.ConfigParser()
        config.read("settings.ini", encoding="utf-8")

        WcApi.login(
            url=config['woocommerce']['url'],
            consumer_key=config['woocommerce']['consumer_key'],
            consumer_secret=config['woocommerce']['consumer_secret'])
        # WcApi.read_only_mode = True

        MSApi.login(config['moy_sklad']['login'], config['moy_sklad']['password'])

        sale_group_tag = config['moy_sklad']['group_tag']
        wc_products = list(gen_all_wc_products())

        assortment_creator = NewAssortmentCreator(wc_products, sale_group_tag)
        products_syncro = ProductsSyncro(wc_products, sale_group_tag)

        try:
            saves_file = open("saves.json", 'r')
            saves_json = json.load(saves_file)
        except FileNotFoundError:
            saves_file = open("saves.json", 'w')
            saves_json = {}
        saves_file.close()

        assortment_blacklist = saves_json.setdefault('assortment_blacklist', [])
        productfolder_blacklist = saves_json.setdefault('productfolder_blacklist', [])

        def func_add_assort_to_blacklist():
            if ms_href in assortment_blacklist:
                print("Assort {} already append to blacklist".format(ms_assort.get_name()))
                return False
            assortment_blacklist.append(ms_href)
            print("Success")
            return True

        def func_add_productfolder_to_blacklist():
            if ms_productfolder is not None:
                if productfolder_href in productfolder_blacklist:
                    print("Productfolder {} already append to blacklist".format(ms_productfolder.get_name()))
                    return False
                productfolder_blacklist.append(ms_productfolder.get_meta().get_href())
                print("Success")
                return True
            else:
                print("Productfolder is None")

        def func_create_new_wc_product():
            try:
                assortment_creator.create_new_product(ms_assort.get_id())
                print("Success")
                return True
            except CheckAssortmentException as exception:
                print(exception)
                return False

        def func_attach_wc_product():
            try:
                wc_id = input("Enter WC_ID:\n")
                products_syncro.attach_wc_product(ms_href, wc_id)
                print("Success")
                return True
            except WcApiException as exception:
                print(exception)
            except SyncroException as exception:
                print(exception)
            except CheckAssortmentException as exception:
                print(exception)
            return False

        def func_detach_wc_product():
            try:
                products_syncro.detach_wc_product(wc_product_id)
                print("Success")
                return True
            except WcApiException as exception:
                print(exception)
            except SyncroException as exception:
                print(exception)
            except CheckAssortmentException as exception:
                print(exception)
            return False

        def func_skip():
            print("Skipped")
            return True

        def func_quit():
            output_file = open("saves.json", 'w')
            json.dump(saves_json, output_file, indent=2)
            output_file.close()
            exit()

        commands = {
            'at': ("Attach WooCommerce product", func_attach_wc_product),
            'dt': ("Detach WooCommerce product", func_detach_wc_product),
            'cr': ("Create new WooCommerce product", func_create_new_wc_product),
            'abl': ("Append assort to blacklist", func_add_assort_to_blacklist),
            'fbl': ("Append productfolder to blacklist", func_add_productfolder_to_blacklist),
            's': ("Skip product", func_skip),
            'quit': ("Save and exit", func_quit)
        }

        dialog = DialogManager("What`s next?\n", commands)
        is_quit = False

        for ms_assort in MSApi.gen_products():
            try:
                ms_productfolder_name = "----"
                productfolder_href = "----"
                ms_productfolder = ms_assort.get_productfolder()
                if ms_productfolder is not None:
                    productfolder_href = ms_productfolder.get_meta().get_href()
                    ms_productfolder_name = ms_productfolder.get_name()

                ms_href = ms_assort.get_meta().get_href()
                wc_product_id = assortment_creator.get_sync_wc_products().get(ms_href)
                print("MS_ID:{}\n\tType: {}\n\tName: {}\n\tAssortment blacklist: {}\n\tProductfolder: {}\n\t"
                      "Productfolder blacklist: {}\n\tWC_ID: {}".format(
                        ms_assort.get_id(),
                        ms_assort.get_meta().get_type(),
                        ms_assort.get_name(),
                        ms_href in assortment_blacklist,
                        ms_productfolder_name,
                        productfolder_href in productfolder_blacklist,
                        wc_product_id))
                ms_id = dialog.main_dialog()
            except CheckAssortmentException as e:
                print(e)

    except ReporterException as e:
        print(e)
    except KeyError as e:
        print(e)
