def double(x): return x * 2
nums = [double(i) for i in range(5)]
gen = (double(i) for i in range(5))
values = list(gen)
words = ['apple', 'banana', 'pear']
sorted_words = sorted(words, key=len)
with open('temp.txt', 'w') as f:
    f.write('hello')
with open('temp.txt', 'r') as f:
    data = f.read()
