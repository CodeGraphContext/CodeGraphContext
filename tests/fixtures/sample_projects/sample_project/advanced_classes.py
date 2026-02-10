from abc import ABC, abstractmethod

class A:
    def foo(self): return 'A'

class B:
    def foo(self): return 'B'

class C(A, B):
    def bar(self): return 'C'

class AbstractThing(ABC):
    @abstractmethod
    def do(self): pass

class ConcreteThing(AbstractThing):
    def do(self): return 'done'

class Meta(type):
    def __new__(mcls, name, bases, dct):
        dct['created_by_meta'] = True
        return super().__new__(mcls, name, bases, dct)

class WithMeta(metaclass=Meta):
    pass

class WithMeta2(metaclass=Meta):
    def __init__(self):
        self.value = 42

    def __str__(self):
        return f"WithMeta2(value={self.value})"

    def change_value(self, new_value):
        self.value = new_value