import enum


class EntityType(enum.StrEnum):
    ORGANIZATION = "organization"


class Entity:

    @classmethod
    def get_entity_type(cls):
        raise NotImplementedError()
