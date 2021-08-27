from MSApi.SubObjectMS import SubObjectMS
from typing import Optional


class Meta(SubObjectMS):
    def __init__(self, json):
        super().__init__(json)

    def __eq__(self, other):
        return self.get_href() == other.get_href()

    def get_href(self) -> str:
        """Ссылка на объект"""
        return self._json.get('href')

    def get_metadata_href(self) -> Optional[str]:
        """Ссылка на метаданные сущности"""
        return self._json.get('href')

    def get_type(self) -> str:
        """Тип объекта"""
        return self._json.get('type')

    def get_media_type(self) -> str:
        """Тип данных, которые приходят в ответ от сервиса, либо отправляются в теле запроса.
        В рамках данного API всегда равен application/json"""
        return self._json.get('mediaType')

    def get_uuid_href(self) -> str:
        """Ссылка на объект на UI. Присутствует не во всех сущностях.
        Может быть использована для получения uuid"""
        return self._json.get('uuidHref')

    def get_download_href(self) -> Optional[str]:
        """Ссылка на скачивание Изображения.
        Данный параметр указывается только в meta для Изображения у Товара или Комплекта."""
        return self._json.get('downloadHref')
