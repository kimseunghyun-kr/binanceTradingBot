# strategyOrchestrator/LoadComponent.py
import importlib

from strategyOrchestrator.entities.config.defaults import DEFAULT_TOKEN


def load_component(spec, builtin, base_cls, label):
    # 1 — resolve object -------------------------------------------------
    if spec in (None, {}, ""):
        obj = builtin[DEFAULT_TOKEN[label]]
    elif isinstance(spec, (int, float, str)):
        obj = builtin[str(spec)]
    elif isinstance(spec, dict) and "builtin" in spec:
        obj = builtin[spec["builtin"]]
    else:
        mod = importlib.import_module(spec["module"])
        obj = getattr(mod, spec["class"])

    # 2 — class handling -------------------------------------------------
    if isinstance(obj, type):
        if base_cls and not issubclass(obj, base_cls):
            raise TypeError(f"{label}: {obj} must subclass {base_cls.__name__}")
        if isinstance(spec, dict) and spec.get("params"):   # instantiate only if params
            return obj(**spec["params"])
        return obj                                          # return class as-is

    # 3 — already callable ----------------------------------------------
    if callable(obj):
        return obj

    raise TypeError(f"{label}: resolved object is neither class nor callable")
