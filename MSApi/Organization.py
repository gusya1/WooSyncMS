from MSApi.ObjectMS import ObjectMS
from MSApi.ObjectMS import check_init

class Organization(ObjectMS):
    def __init__(self, json):
        super().__init__(json)
