
from ProductsSyncro import ProductsSyncro, SyncroException

if __name__ == '__main__':
    try:
        sync = ProductsSyncro("settings.ini", False)
        sync.check_products_part_eq()
    except SyncroException as e:
        print(e)
