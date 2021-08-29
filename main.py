
from ProductsSyncro import ProductsSyncro

from DiscountHandler import DiscountHandler
from MSApi.MSApi import MSApi

if __name__ == '__main__':

    sync = ProductsSyncro("settings.ini")
    # sync.find_duplicate_wc_products()
    sync.sync_products()
    # sync.create_new_wc_products()
    print(sync.report)
    # sync.sync_products()