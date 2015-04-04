def subStringMatch(a, b):
    return a.lower().find(b.lower()) > -1

def subStringMatchQuality(a, b):
    return len(a) > len(b)

def subStringMatchItemsInList(l, key, subString):
    f = lambda item: subStringMatch(item[key], subString)
    return list(filter(f, l))

def subStringMatchItemInList(l, key, subString):
    f = lambda item: subStringMatch(item[key], subString)
    g = lambda a, b: subStringMatchQuality(a[key], b[key])
    
    return findBest(f, g, l)

def subStringMatchDictKey(d, subString):
    f = lambda key: subStringMatch(key, subString)
    g = subStringMatchQuality

    foundKey = findBest(f, g, d)

    if foundKey is not None:
        return d[foundKey]

    return None

def findBest(f, g, seq):
    best = None
    for item in seq:
        if f(item):
            if best is None or g(best, item):
                best = item

    return best

def find(f, seq):
    """Return first item in sequence where f(item) == True."""
    for item in seq:
        if f(item): 
            return item

    return None

def foreach(f, seq):
    for i in seq:
        f(i)


def tryToConvertValue(value, noneValues = []):
    if value is None or value in noneValues:
        return None
    try:
        value = float(value)
    except (ValueError, TypeError) as e:
        pass

    try:
        value = int(value)
    except (ValueError, TypeError) as e:
        pass

    return value

truthValues = ["yes", "true", "1", "t"]
falseValues = ["no", "false", "0", "f"]

def isStrBoolTrue(s, additionalTruthValues = []):
    return s.lower() in truthValues + additionalTruthValues

def isStrBool(s):
    s = s.lower()
    return s in truthValues or s in falseValues

class DictEncapsulator(object):
    def __init__(self, dict = {}):
        self.__assignFromDict(dict)

    def __assignFromDict(self, dict):
        for k, v in dict.items():
            if type(k) is str:
                self.__setattr__(k, v)
