def normalize(x):
    if isinstance(x, str):
        return x.strip().lower()
    return x


def toUpperCase(s):
    return s.upper()


# helper for debugging
# def _dbg(x): print(x)
