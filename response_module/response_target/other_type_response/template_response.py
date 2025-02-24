from response_module.abstract_response import AbstractResponseOther


class TemplateResponse(AbstractResponseOther):
    def __init__(self, config):
        super().__init__(config)

    def send(self, *args, **kwargs):
        print(f'{self.__class__.__name__} send: {args} {kwargs}')
        return True