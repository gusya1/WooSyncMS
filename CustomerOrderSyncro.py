from WcApi import WcApi

import phonenumbers
import logging

from MSApi import Counterparty, MSApi, error_handler, MSApiException, MSApiHttpException, Filter, Organization, Service, \
    Bundle, AttributeMixin
from MSApi import State, Project, Product, Order, Store
from MSApi.documents.CustomerOrder import CustomerOrder

from exceptions import WcApiException

states_dict = {
    "Новый": 'cod',
    "оплачен на сайте": 'tinkoff'
}

projects_dict = {
    'С-Т': 'Пункт №1 ТУХАЧЕВСКОГО',
    'С-П': 'Пункт №2 ПУШКИН'
}

delivery_dict = {
    "Зона №6 (красная зона)": "37d8cd7f-238c-11eb-0a80-046a0001273e",
    "Зона №1 (зелёная зона)": "e4ca996c-238a-11eb-0a80-063300016fe1",
    "Зона №2 (оранжевая зона)": "e4ca996c-238a-11eb-0a80-063300016fe1",
    "Зона №3 (синяя зона)": "a91db949-5572-11eb-0a80-003a0005e730",
    "Зона №4 (фиолетовая зона)": "71dbb4a1-9f5c-11ea-0a80-0404000afc45"
}

store_name = 'Основной склад'

WC_ID_ATTR_NAME = 'wc_id'
IMPORT_FLAG_ATTR_NAME = 'Импортировать в Интернет-магазин'


class CustomerOrderSyncro:

    def __init__(self, customer_tag):
        self.customer_tag = customer_tag
        self.organization: Organization = list(MSApi.gen_organizations())[0]  # TODO choose organization
        for store in Store.gen_list():
            if store.get_name() == store_name:
                self.store: Store = store
                break
        else:
            raise RuntimeError("Store \'{}\' not found".format(store_name))

        self.states_dict = {}
        for state in CustomerOrder.gen_states_list():
            state: State
            payment_method = states_dict.get(state.get_name())
            if payment_method is None:
                continue
            self.states_dict[payment_method] = state
            del states_dict[state.get_name()]
        if len(states_dict) != 0:
            raise RuntimeError("States \'{}\' not found".format(states_dict.keys()))

        self.projects_dict = {}
        for project in Project.gen_list():
            project: Project
            pickup_store_name = projects_dict.get(project.get_name())
            if pickup_store_name is None:
                continue
            self.projects_dict[pickup_store_name] = project
            del projects_dict[project.get_name()]
        if len(projects_dict) != 0:
            raise RuntimeError("Projects \'{}\' not found".format(projects_dict.keys()))

        self.delivery_dict = {}
        for zone_name, service_id in delivery_dict.items():
            service = Service.request_by_id(service_id)
            self.delivery_dict[zone_name] = service

        self.product_wc_id_href = self.__get_attribute_by_name(Product, WC_ID_ATTR_NAME).get_meta().get_href()
        self.product_import_flag_href = self.__get_attribute_by_name(Product,
                                                                     IMPORT_FLAG_ATTR_NAME).get_meta().get_href()
        self.wc_id_attribute = self.__get_attribute_by_name(CustomerOrder, WC_ID_ATTR_NAME)

        for order in MSApi.gen_customer_orders(limit=1, orders=Order.desc('created')):
            self.last_order_num = order.get_name()
        self.last_order_num = int(self.last_order_num)

    @staticmethod
    def __get_attribute_by_name(obj: type(AttributeMixin), name: str):
        for attr in obj.gen_attributes_list():
            if attr.get_name() == name:
                return attr
        raise RuntimeError("{} attribute \'{}\' not found".format(obj.__name__, name))

    @staticmethod
    def __get_bundle_by_wc_id(wc_product_id):
        bundles = []
        for ms_bundle in Bundle.gen_list(cached=True):
            import_flag = ms_bundle.get_attribute_by_name(IMPORT_FLAG_ATTR_NAME)
            if import_flag is None:
                continue
            if not import_flag.get_value():
                continue
            wc_id = ms_bundle.get_attribute_by_name(WC_ID_ATTR_NAME)
            if wc_id is None:
                continue
            if str(wc_product_id) == wc_id.get_value():
                bundles.append(ms_bundle)
        return bundles

    def sync_orders(self):
        start_product_syncro = False
        for wc_order in WcApi.gen_all_wc(entity='orders', filters={'status': 'processing'}, cached=True):
            wc_order_id = wc_order['id']
            try:
                logging.info("WC Order [{}]:\tStarting syncro...".format(wc_order_id))
                ms_cp = self.__find_customer_order_by_phone(wc_order)
                if ms_cp is None:
                    self.__find_customer_order_by_email(wc_order)
                if ms_cp is None:
                    logging.debug("WC Order [{}]:\tCounterparty not found".format(wc_order_id))
                    ms_cp = self.__create_new_counterparty(wc_order)
                if ms_cp is None:
                    raise RuntimeError("Counterparty not found")
                wc_payment_method = wc_order['payment_method']
                state = self.states_dict.get(wc_payment_method)
                if state is None:
                    raise RuntimeError("State for \'{}\' payment method not found".format(wc_payment_method))

                ms_post_order_data = {
                    'description': wc_order.get('customer_note'),
                    'externalCode': str(wc_order.get('id')),
                    'name': str(self.last_order_num + 1).zfill(5),
                    'organization': {'meta': self.organization.get_meta().get_json()},
                    'store': {'meta': self.store.get_meta().get_json()},
                    'state': {'meta': state.get_meta().get_json()},
                    'agent': {'meta': ms_cp.get_meta().get_json()},
                    'attributes': [
                        {
                            'meta': self.wc_id_attribute.get_meta().get_json(),
                            'value': str(wc_order_id)
                        }
                    ]
                }

                project = None
                for meta_data in wc_order['meta_data']:
                    if meta_data['key'] == '_shipping_pickup_stores':
                        project = self.projects_dict.get(meta_data['value'])
                if project is not None:
                    ms_post_order_data['project'] = {'meta': project.get_meta().get_json()}

                positions_post_data_list = []
                for wc_product in wc_order['line_items']:
                    wc_product_id = wc_product['product_id']

                    filters = Filter.eq(self.product_wc_id_href, wc_product_id)
                    filters += Filter.eq(self.product_import_flag_href, True)
                    ms_product_list = list(MSApi.gen_products(filters=filters))
                    ms_product_list += self.__get_bundle_by_wc_id(wc_product_id)
                    if len(ms_product_list) == 0:
                        start_product_syncro = True
                        raise RuntimeError("Product [{}] not found in MoySklad. Assortment syncro will be started"
                                           .format(wc_product_id))
                    elif len(ms_product_list) != 1:
                        raise RuntimeError("Product [{}] multiply definition in MoySklad".format(wc_product_id))
                    ms_product = ms_product_list[0]
                    ms_post_position = {
                        'assortment': {'meta': ms_product.get_meta().get_json()},
                        'quantity': wc_product['quantity'],
                        'price': wc_product['price'] * 100
                    }
                    positions_post_data_list.append(ms_post_position)

                for wc_shipping_line in wc_order['shipping_lines']:
                    service = self.delivery_dict.get(wc_shipping_line['method_title'])
                    if service is None:
                        continue
                    positions_post_data_list.append({
                        'assortment': {'meta': service.get_meta().get_json()},
                        'quantity': 1,
                        'price': int(wc_shipping_line['total']) * 100
                    })
                ms_post_order_data['positions'] = positions_post_data_list

                try:
                    response = MSApi.auch_post("entity/customerorder", json=ms_post_order_data)
                    error_handler(response)
                    ms_order = CustomerOrder(response.json())
                    logging.info('WC Order [{}]: CustomerOrder {} created'.format(wc_order_id, ms_order.get_name()))
                    self.last_order_num += 1
                    wc_put_data = {
                        'status': 'completed'
                    }
                    WcApi.put('orders/{}'.format(wc_order['id']), data=wc_put_data)
                except WcApiException as e:
                    logging.error('WC Order status change failed: {}'.format(str(e)))
            except RuntimeError as e:
                logging.error("WC Order [{}]: Synchronize failed: {}".format(wc_order_id, str(e)))
            except MSApiException as e:
                logging.error("WC Order [{}]: MoySklad error: {}".format(wc_order_id, str(e)))
        return start_product_syncro

    @staticmethod
    def check_and_correct_ms_phone_numbers():
        """проверяет формат телефонных номеров контрагентов и исправляет при необходимости"""
        try:
            for ms_cp in Counterparty.gen_list():
                ms_cp: Counterparty
                ms_cp_phone = ms_cp.get_phone()
                if ms_cp_phone is None:
                    continue

                try:
                    ms_number = phonenumbers.parse(ms_cp_phone, "RU")
                    ms_formatted_number = phonenumbers.format_number(ms_number, phonenumbers.PhoneNumberFormat.E164)
                    if ms_formatted_number == ms_cp_phone:
                        continue

                    response = MSApi.auch_put("entity/counterparty/{}".format(ms_cp.get_id()), json={
                        'phone': ms_formatted_number
                    })
                    error_handler(response)
                    logging.info("Counterparty \"{}\": phone format from \'{}\' to \'{}\'".format(
                        ms_cp.get_name(),
                        ms_cp_phone,
                        ms_formatted_number
                    ))
                except phonenumbers.phonenumberutil.NumberParseException:
                    logging.warning(f"Counterparty \"{ms_cp.get_name()}\": Invalid phone: {ms_cp_phone}")
                except MSApiHttpException as e:
                    logging.error(str(e))
        except MSApiException as e:
            logging.error(str(e))

    @staticmethod
    def __find_customer_order_by_phone(wc_order):
        """ищет контрагента по номеру телефона"""
        wc_phone_str = wc_order.get('billing').get('phone')
        if wc_phone_str == '':
            logging.debug("WC Order [{}]:\tPhone is empty".format(wc_order.get('id')))
            return None
        try:
            wc_number = phonenumbers.parse(wc_phone_str, "RU")
            formatted_number = phonenumbers.format_number(wc_number, phonenumbers.PhoneNumberFormat.E164)

            ms_cp_list = list(Counterparty.gen_list(filters=Filter.eq('phone', formatted_number)))
            if not ms_cp_list:
                logging.debug("WC Order [{}]:\tCounterparty not found by phone".format(wc_order.get('id')))
                return None
            elif len(ms_cp_list) > 1:
                logging.warning("WC Order [{}]: Phone number \'{}\' multiply definition in MoySklad".format(
                    wc_order.get('id'), formatted_number))
            else:
                logging.debug("WC Order [{}]: Counterparty \'{}\' found by phone".format(wc_order.get('id'),
                                                                                         ms_cp_list[0].get_name()))
            return ms_cp_list[0]
        except phonenumbers.phonenumberutil.NumberParseException:
            logging.warning("WC Order [{}]:\tInvalid phone \'{}\'".format(wc_order.get('id'), wc_phone_str))
            return None

    @staticmethod
    def __find_customer_order_by_email(wc_order):
        """ищет контрагента по эллектронному адресу"""
        wc_email_str = wc_order.get('billing').get('email')
        if wc_email_str == '':
            logging.debug("WC Order [{}]:\tEmail is empty".format(wc_order.get('id')))
            return None

        ms_cp_list = list(Counterparty.gen_list(filters=Filter.eq('email', wc_email_str)))
        if not ms_cp_list:
            logging.debug("WC Order [{}]:\tCounterparty not found by email".format(wc_order.get('id')))
            return None
        elif len(ms_cp_list) > 1:
            logging.warning("WC Order [{}]: Email \'{}\' multiply definition in MoySklad".format(wc_order.get('id'),
                                                                                                 wc_email_str))
            return None
        else:
            logging.debug("WC Order [{}]: Counterparty \'{}\' found by email".format(wc_order.get('id'),
                                                                                     ms_cp_list[0].get_name()))
            return ms_cp_list[0]

    def __create_new_counterparty(self, wc_order):

        phone = self.__get_format_phone_by_order(wc_order)
        if phone is None:
            phone = wc_order.get('billing').get('phone')

        cp_name = self.__get_name_by_order(wc_order, phone)

        ms_post_data = {
            'name': "{}".format(cp_name),
            'phone': phone,
            'email': wc_order.get('billing').get('email'),
            'actualAddress': wc_order.get('billing').get('address_1'),
            'tags': [self.customer_tag]
        }
        logging.debug("Creating new counterparty: {}".format(ms_post_data))
        response = MSApi.auch_post('entity/counterparty', json=ms_post_data)
        error_handler(response)
        logging.info("New counterparty \'{}\' created".format(cp_name))
        return Counterparty(response.json())

    @staticmethod
    def __get_name_by_order(wc_order, phone):
        wc_billing = wc_order.get('billing')
        return "NEW {} {} {}".format(wc_billing.get('first_name'),
                                     wc_billing.get('last_name'),
                                     phone)

    @staticmethod
    def __get_format_phone_by_order(wc_order):
        wc_phone_str = wc_order.get('billing').get('phone')
        if wc_phone_str == '':
            logging.warning("WC Order [{}]:\tPhone is empty".format(wc_order.get('id')))
            return None
        try:
            wc_number = phonenumbers.parse(wc_phone_str, "RU")
            return phonenumbers.format_number(wc_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException:
            logging.warning("WC Order [{}]:\tInvalid phone \'{}\'".format(wc_order.get('id'), wc_phone_str))
        return None
