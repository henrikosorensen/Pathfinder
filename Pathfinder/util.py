def subStringMatchItemsInList(l, key, subString):
    f = lambda item : item[key].lower().find(subString.lower()) > -1
    return filter(f, l)        

def subStringMatchItemInList(l, key, subString):
    m = subStringMatchItemsInList(l, key, subString)
    if m != []:
        return m[0]
    else:
        return None

def subStringMatchDictKey(d, subString):
    f = lambda key : key.lower().find(subString.lower()) > -1
    foundKey = find(f, d)

    if foundKey is not None:
        return (foundKey, d[foundKey])
    return None

def find(f, seq):
    """Return first item in sequence where f(item) == True."""
    for item in seq:
        if f(item): 
            return item

    return None

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

def getGoldValue(pp, gp, sp, cp):
    return (pp * 10) + gp + sp / 10.0 + cp / 100.0

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
