from ..parent_mod import parent_function, ParentClass

def child_function():
    # Calling function from parent package using relative import
    return parent_function() + " -> and Child"

class ChildClass(ParentClass):
    def greet(self):
        # Calling inherited method via super()
        return super().greet() + " (and Child)"
