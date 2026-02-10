def gen_numbers(n):
    for i in range(n):
        yield i

async def agen_numbers(n):
    for i in range(n):
        yield i

async def async_with_example():
    async with AsyncCM() as val:
        return val

class AsyncCM:
    async def __aenter__(self): return 'async_entered'
    async def __aexit__(self, exc_type, exc_val, exc_tb): return False
