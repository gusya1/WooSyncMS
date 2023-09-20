import api

from moy_sklad_models.attribute import Attribute


def gen_attributes_list(session, type_name):
    response = session.get(f"entity/{type_name}/metadata/attributes")
    api.error_handler(response)
    for attribute_json in response.json()["rows"]:
        yield Attribute(init=attribute_json)
