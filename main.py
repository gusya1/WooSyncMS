
from ProductsSyncro import ProductsSyncro

if __name__ == '__main__':
    sync = ProductsSyncro("settings.ini")
    sync.check_products_part_eq()
