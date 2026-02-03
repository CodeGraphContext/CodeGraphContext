class Base:
    def greet(self):
        return "hello"

class Child(Base):
    def greet(self):
        return super().greet() + " world"

    @staticmethod
    def static_method(x):
        return x * 2

    @classmethod
    def class_method(cls, y):
        return cls().greet(cls()) + str(y)

def decorator(func):
    def wrapper(*args, **kwargs):
        return "decorated: " + str(func(*args, **kwargs))
    return wrapper

@decorator
def decorated_function(x):
    return x + 10
