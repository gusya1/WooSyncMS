from MSApi.SubObjectMS import SubObjectMS
from MSApi.Meta import Meta
from MSApi.MSLowApi import MSLowApi


def check_init(method):
    def wrapper(*args, **kwargs):
        if len(args[0].get_json()) == 1:
            args[0].set_json(MSLowApi.get_json_by_href(args[0].get_meta().get_href()))
        return method(*args, **kwargs)
    return wrapper


class ObjectMS(SubObjectMS):

    def __init__(self, json):
        super().__init__(json)

    def __eq__(self, other):
        return self.get_meta() == other.get_meta()

    def get_meta(self):
        return Meta(self._json.get('meta'))

    def get_json(self):
        return self._json

    def set_json(self, json):
        self._json = json.copy()
