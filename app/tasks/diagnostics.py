import inspect

def _find_coroutines(obj, path="root"):
    """
    Recursively walk dicts/lists/tuples to find any coroutine objects.
    Returns a list of paths where a coroutine was found.
    """
    bad = []
    if inspect.iscoroutine(obj):
        bad.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            bad += _find_coroutines(v, f"{path}.{k!r}")
    elif isinstance(obj, (list, tuple)):
        for idx, v in enumerate(obj):
            bad += _find_coroutines(v, f"{path}[{idx}]")
    return bad