from response_module.abstract_response import AbstractResponseOther


class TemplateResponse(AbstractResponseOther):
    def __init__(self, config):
        """
        Initializes a TemplateResponse instance with the given configuration.
        
        Args:
            config: Configuration settings used to initialize the response.
        """
        super().__init__(config)

    def send(self, *args, **kwargs):
        """
        Print the class name and provided arguments, then return True.
        
        This method outputs a formatted message to stdout that includes the name of the class
        along with any positional and keyword arguments passed to it.
        
        Returns:
            bool: Always returns True.
        """
        print(f'{self.__class__.__name__} send: {args} {kwargs}')
        return True