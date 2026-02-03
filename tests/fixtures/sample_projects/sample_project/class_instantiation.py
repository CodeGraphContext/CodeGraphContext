class A:
    def greet(self): return 'Hello from A'

class B(A):
    def greet(self): return super().greet() + ' + B'

obj = A()
msg1 = obj.greet()
obj2 = B()
msg2 = obj2.greet() 

class Fluent:
    def step1(self): return self
    def step2(self): return self
    def step3(self): return self

f = Fluent().step1().step2().step3()

obj2.dynamic = lambda x: x * 2
val = obj2.dynamic(10)
