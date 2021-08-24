from MSApi.ObjectMS import ObjectMS


class Template(ObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def get_name(self):
        return self._json.get('name')
