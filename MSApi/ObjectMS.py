from MSApi.SubObjectMS import SubObjectMS
from MSApi.Meta import Meta
# from MSApi.MSApi import MSApi


class ObjectMS(SubObjectMS):

    def __init__(self, json):
        super().__init__(json)
        # if len(self.get_json()) == 1:
        #     self._json = MSApi.get_object_by_meta(self.get_meta())

    def __eq__(self, other):
        return self.get_meta() == other.get_meta()

    def get_meta(self):
        return Meta(self._json.get('meta'))

    def get_json(self):
        return self._json
