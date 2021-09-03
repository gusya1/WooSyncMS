import requests

from MSApi.exceptions import *
from MSApi.properties import *

ms_url = "https://online.moysklad.ru/api/remap/1.2"


def error_handler(response: requests.Response, expected_code=200):
    code = response.status_code
    if code == expected_code:
        return

    raise MSApiHttpException(response)


class Authorizer:
    __token = None

    @classmethod
    def login(cls, login: str, password: str):
        import base64
        auch_base64 = base64.b64encode(f"{login}:{password}".encode('utf-8')).decode('utf-8')
        response = requests.post(f"{ms_url}/security/token",
                                 headers={"Authorization": f"Basic {auch_base64}"})
        error_handler(response, 201)
        cls.__token = str(response.json()["access_token"])

    @classmethod
    def is_auch(cls) -> bool:
        return cls.__token is not None

    @classmethod
    def get_token(cls):
        return cls.__token


class MSLowApi:
    __authorizer = Authorizer()

    @classmethod
    def login(cls, login: str, password: str):
        cls.__authorizer.login(login, password)

    @classmethod
    def check_login(cls, f):
        if cls.__authorizer.is_auch():
            raise MSApiException("Login first")
        return f

    @classmethod
    def get_json_by_href(cls, href):
        response = cls._auch_get_by_href(href)
        error_handler(response)
        return response.json()

    @classmethod
    # @check_login
    def __auch_post(cls, request, **kwargs):
        return requests.post(f"{ms_url}/{request}",
                             headers={"Authorization": f"Bearer {cls.__authorizer.get_token()}",
                                      "Content-Type": "application/json"},
                             **kwargs)

    @classmethod
    def auch_get(cls, request, **kwargs):
        return cls._auch_get_by_href(f"{ms_url}/{request}", **kwargs)

    @classmethod
    # @check_login
    def _auch_get_by_href(cls, request, search: Search = None, filters: Filter = None, expand: Expand = None, **kwargs):
        params = []
        if search is not None:
            params.append(str(search))
        if filters is not None:
            params.append(str(filters))
        if expand is not None:
            params.append(str(expand))
        params_str = ""
        if params:
            params_str = f"?{'&'.join(params)}"

        return requests.get(f"{request}{params_str}",
                            headers={"Authorization": f"Bearer {cls.__authorizer.get_token()}",
                                     "Content-Type": "application/json"},
                            **kwargs)
