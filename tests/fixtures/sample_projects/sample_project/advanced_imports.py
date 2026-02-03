def outer_import():
    import math
    return math.sqrt(25)

if True:
    import random
else:
    import sys

def use_random():
    return random.randint(1, 10)
