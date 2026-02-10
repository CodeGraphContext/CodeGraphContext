from functools import partial
import operator
import importlib

def add(a, b): return a + b
def sub(a, b): return a - b
def mul(a, b): return a * b

DISPATCH = {'add': add, 'sub': sub, 'mul': mul}

def dispatch_by_key(name, a, b):
    return DISPATCH[name](a, b)

def dispatch_by_string(name, *args, **kwargs):
    fn = globals().get(name)
    if callable(fn):
        return fn(*args, **kwargs)
    raise KeyError(name)

def partial_example():
    add5 = partial(add, 5)
    return add5(10)

class C:
    def method(self, x): return x + 3

def methodcaller_example(x):
    c = C()
    mc = operator.methodcaller('method', x)
    return mc(c)

def dynamic_import_call(mod_name, fn_name, *args, **kwargs):
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, fn_name)
    return fn(*args, **kwargs)
