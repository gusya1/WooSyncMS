from typing import Union

from pydantic import BaseModel

from model_types import UUID, Meta, DateTime
import entity


class Organization(BaseModel, entity.Entity):
    accountId: UUID
    actualAddress: str
    actualAddressFull: {}  # TODO make a model
    archived: bool
    bonusPoints: int
    bonusProgram: Meta
    code: str
    companyType: str  # TODO make a model
    created: DateTime
    description: str
    externalCode: str
    group: Meta
    id: UUID
    meta: Meta
    name: str
    owner: Meta
    shared: bool
    syncId: UUID
    trackingContractDate: DateTime
    trackingContractNumber: str
    updated: DateTime

    @classmethod
    def get_entity_type(cls):
        return entity.EntityType.ORGANIZATION
