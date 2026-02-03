from dataclasses import dataclass
import enum
from collections import namedtuple

@dataclass
class Point:
    x: int
    y: int

class Color(enum.Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

Person = namedtuple('Person', ['name', 'age'])
