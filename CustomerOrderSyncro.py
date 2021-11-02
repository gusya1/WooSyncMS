from WcApi import WcApi

import phonenumbers
import logging

from MSApi import Counterparty, MSApi, error_handler, MSApiException, MSApiHttpException, Filter


class CustomerOrderSyncro:

    def __init__(self, customer_tag):
        self.customer_tag = customer_tag

    def sync_orders(self):
        for wc_order in WcApi.gen_all_wc(entity='orders', filters={'status': 'processing'}):
            ms_cp = self.__find_customer_order_by_phone(wc_order)
            if ms_cp is None:
                self.__find_customer_order_by_email(wc_order)
            if ms_cp is None:
                pass
                # logging.debug("WC Order [{}]:\tCounterparty not found".format(wc_order.get('id')))



    def check_and_correct_ms_phone_numbers(self):
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
                    logging.info("Phone number in \'{}\' counterparty format from \'{}\' to \'{}\'".format(
                        ms_cp.get_name(),
                        ms_cp_phone,
                        ms_formatted_number
                    ))
                except phonenumbers.phonenumberutil.NumberParseException as e:
                    logging.error(f"Invalid phone: {ms_cp_phone}")
                except MSApiHttpException as e:
                    logging.error(str(e))
        except MSApiException as e:
            logging.error(str(e))

    def __find_customer_order_by_phone(self, wc_order):
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
                logging.error("Phone number \'{}\' duplicated".format(wc_order.get('id'), formatted_number))
                return None
            else:
                logging.debug("WC Order [{}]: Counterparty \'{}\' found by phone".format(wc_order.get('id'),
                                                                                         ms_cp_list[0].get_name()))
                return ms_cp_list[0]
        except phonenumbers.phonenumberutil.NumberParseException as e:
            logging.warning("WC Order [{}]:\tInvalid phone \'{}\'".format(wc_order.get('id'), wc_phone_str))
            return None

    def __find_customer_order_by_email(self, wc_order):
        wc_email_str = wc_order.get('billing').get('email')
        if wc_email_str == '':
            logging.debug("WC Order [{}]:\tEmail is empty".format(wc_order.get('id')))
            return None

        ms_cp_list = list(Counterparty.gen_list(filters=Filter.eq('email', wc_email_str)))
        if not ms_cp_list:
            logging.debug("WC Order [{}]:\tCounterparty not found by email".format(wc_order.get('id')))
            return None
        elif len(ms_cp_list) > 1:
            logging.warning("Phone number \'{}\' duplicated".format(wc_order.get('id'), wc_email_str))
            return None
        else:
            logging.debug("WC Order [{}]: Counterparty \'{}\' found by email".format(wc_order.get('id'),
                                                                                     ms_cp_list[0].get_name()))
            return ms_cp_list[0]

    def __create_new_counterparty(self, wc_order):
        ms_post_data = {
            'name': self.__get_name_by_order(wc_order),
            'phone': self.__get_format_phone_by_order(wc_order),
            'email': wc_order.get('billing').get('email'),
            'tags': [self.customer_tag]
        }
        logging.debug("Creating new counterparty: {}".format(ms_post_data))

    def __get_name_by_order(self, wc_order):
        wc_billing = wc_order.get('billing')
        return "{} {} {}".format(wc_billing.get('first_name'),
                                 wc_billing.get('last_name'),
                                 self.__get_format_phone_by_order(wc_order) or "")

    def __get_format_phone_by_order(self, wc_order):
        wc_phone_str = wc_order.get('billing').get('phone')
        if wc_phone_str == '':
            logging.debug("WC Order [{}]:\tPhone is empty".format(wc_order.get('id')))
            return None
        try:
            wc_number = phonenumbers.parse(wc_phone_str, "RU")
            return phonenumbers.format_number(wc_number, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.phonenumberutil.NumberParseException as e:
            logging.warning("WC Order [{}]:\tInvalid phone \'{}\'".format(wc_order.get('id'), wc_phone_str))
        return None
