from MSApi.ObjectMS import ObjectMS
from typing import Optional


class PriceType(ObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def get_id(self) -> str:
        return self._json.get('id')

    def get_name(self) -> str:
        return self._json.get('name')

    def get_external_code(self) -> str:
        return self._json.get('externalCode')
