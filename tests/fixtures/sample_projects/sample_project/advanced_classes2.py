from dataclasses import dataclass
from enum import Enum

class Base: pass
class Mid(Base): pass
class Final(Mid): pass

class Mixin1:
    def m1(self): return 'm1'
class Mixin2:
    def m2(self): return 'm2'

class Combined(Mixin1, Mixin2, Base):
    def both(self): return self.m1() + self.m2()

c = Combined()
res = c.both()

@dataclass
class Point:
    x: int
    y: int
    def magnitude(self): return (self.x ** 2 + self.y ** 2) ** 0.5

p = Point(3,4)
dist = p.magnitude()

class Color(Enum):
    RED = 1
    BLUE = 2
    def is_primary(self): return self in {Color.RED, Color.BLUE}

flag = Color.RED.is_primary()

def handle(val):
    match val:
        case Point(x, y):
            return f'Point with magnitude {val.magnitude()}'
        case _:
            return 'Unknown'
msg = handle(p)
