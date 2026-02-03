def executor(func, val):
    return func(val)

def square(x): return x * x
res = executor(square, 5)

def log_decorator(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

@log_decorator
def hello(name): return f'Hello {name}'

msg = hello('Shashank')
