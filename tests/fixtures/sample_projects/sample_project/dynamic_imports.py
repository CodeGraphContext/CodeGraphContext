import importlib

def import_optional():
    try:
        import ujson as json
    except ImportError:
        import json
    return json.dumps({'a': 1})

def import_by___import__(name):
    mod = __import__(name)
    return getattr(mod, 'platform', None)

def importlib_runtime(name, attr=None):
    mod = importlib.import_module(name)
    if attr:
        return getattr(mod, attr)
    return mod
