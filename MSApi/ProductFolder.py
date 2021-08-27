from MSApi.ObjectMS import ObjectMS, SubObjectMS


class ProductFolder(ObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def get_name(self) -> str:
        return self._json.get('name')

    def get_id(self) -> str:
        return self._json.get('id')