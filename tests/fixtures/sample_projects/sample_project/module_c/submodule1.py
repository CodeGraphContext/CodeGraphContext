from module_b import helper

def call_helper_twice(x):
    return helper(x) + helper(x + 1)
