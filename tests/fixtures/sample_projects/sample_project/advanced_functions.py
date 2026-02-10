def with_defaults(a, b=5, c='hello'):
    return f"{a}-{b}-{c}"

def with_args_kwargs(*args, **kwargs):
    return args, kwargs

def higher_order(func, data):
    return [func(x) for x in data]

def return_function(x):
    def inner(y):
        return x + y
    return inner
