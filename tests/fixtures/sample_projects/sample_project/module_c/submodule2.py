from module_c.submodule1 import call_helper_twice

def wrapper(x):
    return call_helper_twice(x) * 2
