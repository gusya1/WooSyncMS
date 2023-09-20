import requests
from requests import Response
from requests.adapters import HTTPAdapter, Retry
from requests.models import PreparedRequest

from exceptions import HttpException

from moy_sklad_models.entity import Entity, EntityType

import logging
import urllib


_ms_url = "https://online.moysklad.ru/api/remap/1.2"


def error_handler(response: Response, expected_code=200):
    code = response.status_code
    if code == expected_code:
        return
    raise HttpException(response)


class Session:
    def __init__(self):
        self.__logger = logging.Logger("MoySklad API")
        self.__session = requests.Session()
        self.__token = None

    def login(self, login: str, password: str):
        import base64
        auch_base64 = base64.b64encode(f"{login}:{password}".encode('utf-8')).decode('utf-8')

        response = self.__session.post(f"{_ms_url}/security/token",
                                headers={"Authorization": f"Basic {auch_base64}"})
        error_handler(response, 201)
        self.__token = str(response.json()["access_token"])

    def set_access_token(self, access_token: str):
        self.__token = access_token

    def get(self, request: str, **kwargs):
        self.__logger.debug(f"GET: {request}")
        urllib.parse.quote(request)
        return self.__session.get(f"{_ms_url}/{request}",
                                  headers={"Authorization": f"Bearer {self.__token}",
                                          "Content-Type": "application/json"},
                                  **kwargs)

    def post(self, request, **kwargs):
        self.__logger.debug(f"POST: {request}")
        request = urllib.parse.quote(request)
        return self.__session.post(f"{_ms_url}/{request}",
                                   headers={"Authorization": f"Bearer {self.__token}",
                                           "Content-Type": "application/json"},
                                   **kwargs)

    def put(self, request, **kwargs):
        self.__logger.debug(f"PUT: {request}")
        request = urllib.parse.quote(request)
        return self.__session.put(f"{_ms_url}/{request}",
                                  headers={"Authorization": f"Bearer {self.__token}",
                                          "Content-Type": "application/json"},
                                  **kwargs)

    def gen_all_objects(self, entity_type: type(Entity), **kwargs):
        limit = 100
        params = {
            "limit": limit,
            "expand": True,
            "offset": 0
        }
        while True:
            request = PreparedRequest()
            request.prepare_url('entity/{}'.format(entity_type.get_entity_type()), params)
            response = self.get(request.url, **kwargs)
            error_handler(response)

            row_counter = 0
            for row in response.json().get('rows'):
                yield entity_type(init=row)
                row_counter += 1
            if row_counter == 0:
                break
            params["offset"] += limit
            if limit is None:
                continue
            limit -= local_limit
            if limit < local_limit:
                local_limit = limit
            if local_limit == 0:
                break
        return self.get('entity/{}'.format(entity_type.get_entity_type()), **kwargs)
