def matcher(x):
    match x:
        case 0: return 'zero'
        case 1 | 2: return 'one or two'
        case str() as s: return f'string: {s}'
        case _: return 'other'
