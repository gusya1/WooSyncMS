
class ObjectMS:
    def __init__(self, json):
        self._json = json

    def get_meta(self):
        return self._json.get('meta')

    def get_json(self):
        return self._json


class SubObjectMS:
    def __init__(self, json):
        self._json = json

    def get_json(self):
        return self._json
