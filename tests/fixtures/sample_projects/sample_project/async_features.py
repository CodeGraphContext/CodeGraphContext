import asyncio

async def fetch_data(x):
    await asyncio.sleep(0)
    return x * 2

async def main():
    result = await fetch_data(10)
    return result
