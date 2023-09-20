import pydantic
import datetime

UUID = str
URL = str
DateTime = datetime.datetime


class Meta(pydantic.BaseModel):
    href: URL
    metadataHref: URL
    type: str
    mediaType: str
    uuidHref: URL
    downloadHref: URL = None
