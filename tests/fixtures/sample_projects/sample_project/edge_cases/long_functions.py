def long_loop_example(n):
    result = []
    for i in range(n):
        if i % 2 == 0:
            result.append(i * 2)
        else:
            result.append(i + 3)
        if i % 5 == 0:
            result.append(i - 1)
        if i % 7 == 0:
            result.append(i * i)
        if i % 3 == 0:
            result.append(i // 2)
        if i % 4 == 0:
            result.append(i + 10)
        if i % 6 == 0:
            result.append(i - 5)
        if i % 8 == 0:
            result.append(i * 3)
        if i % 9 == 0:
            result.append(i + 7)
        if i % 10 == 0:
            result.append(i - 2)
    return result

def verbose_conditions(x, y):
    if x > 0:
        a = x + y
    else:
        a = x - y
    if y > 0:
        b = y * 2
    else:
        b = y // 2
    if x == y:
        c = x * y
    else:
        c = x + y
    if x % 2 == 0:
        d = x // 2
    else:
        d = x * 2
    if y % 3 == 0:
        e = y // 3
    else:
        e = y * 3
    if x > 10:
        f = x - 10
    else:
        f = x + 10
    return a + b + c + d + e + f

def extended_try_except(val):
    try:
        if val < 0:
            raise ValueError("Negative value")
        elif val == 0:
            raise ZeroDivisionError("Zero value")
        elif val > 100:
            raise OverflowError("Too large")
        result = val * 2
        for i in range(5):
            result += i
        if result % 2 == 0:
            result //= 2
        else:
            result += 1
        return result
    except ValueError as ve:
        return str(ve)
    except ZeroDivisionError as zde:
        return str(zde)
    except OverflowError as oe:
        return str(oe)
    except Exception as e:
        return "Unknown error: " + str(e)
    finally:
        _ = "done"