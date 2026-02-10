def square(x): return x * x

def calls():
    data = [1, 2, 3]
    result1 = [square(x) for x in data]
    result2 = list(map(square, data))
    obj = Dummy()
    result3 = getattr(obj, 'method')(5)
    return result1, result2, result3

class Dummy:
    def method(self, x): return x + 10
