from strategyOrchestrator.entities.strategies.BaseStrategy import BaseStrategy


class ParametrizedStrategy(BaseStrategy):
    """
    Optional adapter/intermediate class that manages user parameters
    and provides hooks for more complex strategies.

    Subclasses can:
      - Set and validate custom parameters at construction or runtime
      - Override set_params() for validation or param-dependent setup
      - Retrieve all user parameters cleanly via get_params()
    """

    def __init__(self, **params):
        super().__init__()
        self.set_params(**params)

    def set_params(self, **params):
        """
        Set user-defined parameters for this strategy.
        Subclasses can override for validation (e.g. type checks, value ranges).
        """
        # Call parent (in case of multiple inheritance)
        if hasattr(super(), "set_params"):
            super().set_params(**params)
        for k, v in params.items():
            setattr(self, k, v)
        # Optionally add: self._validate_params()

    def get_params(self):
        """
        Return a dictionary of current parameters for logging or tuning.
        Filters out internal/callable/dunder attributes.
        """
        return {
            k: v
            for k, v in self.__dict__.items()
            if not k.startswith('_') and not callable(v) and not (k.startswith('__') and k.endswith('__'))
        }

    def _validate_params(self):
        """
        (Optional) Validation logic for parameter values. Subclass as needed.
        """
        pass
