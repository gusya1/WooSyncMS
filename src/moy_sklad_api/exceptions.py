from json.decoder import JSONDecodeError


class MoySkladApiError(Exception):
    pass


class HttpException(MoySkladApiError):
    def __init__(self, response):
        self.errors = []
        self.status_code = response.status_code
        try:
            json = response.json()
            if json is list:
                for local in json:
                    for json_error in local.get('errors'):
                        self.errors.append(json_error.get('error'))
            else:
                for json_error in json.get('errors'):
                    self.errors.append(json_error.get('error'))
        except JSONDecodeError as e:
            self.errors.append(str(response.text))

    def __str__(self):
        return '[{}] {}'.format(self.status_code, "\n".join(self.errors))
