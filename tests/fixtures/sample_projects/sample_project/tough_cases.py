import functools
import sys

"""
Tough Case 1: Complex Decorator Chains with Arguments
Tests if the indexer can track the original function through multiple layers of wrapping.
"""
def debug_logger(prefix=""):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(f"{prefix} Calling {func.__name__}")
            result = func(*args, **kwargs)
            print(f"{prefix} {func.__name__} returned {result}")
            return result
        return wrapper
    return decorator

class Service:
    @debug_logger(prefix="[API]")
    def process_data(self, data):
        return f"Processed {data}"

"""
Tough Case 2: Metaclass Method Injection
Tests if the indexer can detect methods that aren't explicitly in the class body.
"""
class MethodInjector(type):
    def __new__(cls, name, bases, dct):
        def dynamic_method(self):
            return f"I am a dynamic method in {name}"
        dct['injected_call'] = dynamic_method
        return super().__new__(cls, name, bases, dct)

class MagicClass(metaclass=MethodInjector):
    def static_method(self):
        return self.injected_call() # Calling a method injected by metaclass

"""
Tough Case 3: Dynamic Calls via getattr and globals()
"""
def hidden_function():
    return "You found me!"

class DynamicCaller:
    def call_by_name(self, func_name):
        # Calling via globals()
        if func_name in globals():
            return globals()[func_name]()
        
        # Calling via getattr
        method = getattr(self, 'helper_method', None)
        if method:
            return method()

    def helper_method(self):
        return "Helper called"

"""
Tough Case 4: Deeply Nested Scopes and Shadowing
"""
def outer_scope():
    x = "outer"
    def middle_scope():
        nonlocal x
        x = "middle"
        def inner_scope():
            x = "inner" # Shadowing
            return x
        return inner_scope()
    return middle_scope()

"""
Tough Case 5: Conditional Imports and Logic
"""
if sys.platform == "win32":
    def platform_action(): return "Windows logic"
else:
    def platform_action(): return "Posix logic"

class PlatformManager:
    def run(self):
        return platform_action()
