def core_function(): return 'core'

def reexport(): return core_function()

import math as m
val = m.sqrt(16)
