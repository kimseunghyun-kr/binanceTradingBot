from strategies.BaseStrategy import BaseStrategy

class ParametrizedStrategy(BaseStrategy):
    """
    Optional adapter/intermediate class that manages parameters,
    and provides hooks for more complex strategies.
    """
    def __init__(self, **params):
        super().__init__()
        self.set_params(**params)

    def set_params(self, **params):
        """
        Overwrite to validate or handle params.
        """
        for k, v in params.items():
            setattr(self, k, v)
        # You could add validation logic here

    def get_params(self):
        """
        Return dict of current params.
        """
        # Could filter only allowed params
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
