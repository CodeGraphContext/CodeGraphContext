import os

def choose_path(x):
    if x > 0: return 'positive'
    elif x == 0: return 'zero'
    else: return 'negative'

def ternary(x):
    return 'pos' if x > 0 else 'non-pos'

def try_except_finally(x):
    try:
        if x == 0:
            raise ValueError('zero')
        return 10 / x
    except ValueError as e:
        return str(e)
    except Exception:
        return None
    finally:
        _ = 'cleaned'

def conditional_inner_import(use_numpy=False):
    if use_numpy:
        import numpy as np
        return np.array([1, 2, 3])
    else:
        return [1, 2, 3]

def env_based_import():
    if os.getenv('USE_UJSON') == '1':
        try:
            import ujson as json
        except Exception:
            import json
    else:
        import json
    return json.dumps({'a': 1})
