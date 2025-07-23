import importlib
from typing import Callable, Any, Type, Dict


def load_component(
    spec: Any,
    builtin: Dict[str, Any],
    base_cls: Type | None,
    label: str,
) -> Callable:
    """
        Returns a **callable** ready for injection.

        Accepts shorthands:
          • scalar (0.0005)                    -> builtin lookup
          • {"builtin":"token",   "params":{}} -> builtin entry
          • {"module":"x.y", "class":"Cls", "params":{}} -> dynamic import
        """

    # 1 — resolve obj ----------------------------------------------------
    if spec is None or spec == {}:
        obj = builtin["__default__"]

    elif isinstance(spec, (int, float, str)):
        obj = builtin.get(str(spec))
        if obj is None:
            raise ValueError(f"{label}: unknown shorthand '{spec}'")

    elif "builtin" in spec:
        obj = builtin[spec["builtin"]]

    else:
        mod = importlib.import_module(spec["module"])
        obj = getattr(mod, spec["class"])

    # 2 — instantiate class ---------------------------------------------
    if isinstance(obj, type):
        if base_cls and not issubclass(obj, base_cls):
            raise TypeError(f"{label}: {obj} must subclass {base_cls.__name__}")
        return obj(**spec.get("params", {}))

    # 3 — already callable ----------------------------------------------
    if callable(obj):
        return obj

    raise TypeError(f"{label}: resolved object is neither class nor callable")