from typing import List, Dict, Union

def typed_func(a: int, b: str) -> List[str]:
    return [b] * a

def union_func(x: Union[int, str]) -> str:
    return str(x)

def dict_func(d: Dict[str, int]) -> int:
    return sum(d.values())
