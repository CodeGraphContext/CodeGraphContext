def f1(x): return x + 1
def f2(x): return x * 2
def f3(x): return x - 3

result = f1(f2(f3(10)))

text = '  Hello World  '
cleaned = text.strip().lower().replace('hello', 'hi')

def make_adder(n):
    def adder(x):
        return x + n
    return adder

adder5 = make_adder(5)
result2 = adder5(10)
result3 = make_adder(2)(8)
