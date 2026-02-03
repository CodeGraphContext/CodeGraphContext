import math
import module_b as mb
from module_b import process_data

def foo(x):
    return mb.helper(x) + mb.value + process_data([x])

def bar():
    return math.sqrt(16)

nested = lambda x: x * 2

def outer():
    def inner(y):
        return y + 1
    return inner(5)
