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
    f = lambda k : k.lower().find(subString.lower()) > -1
    m = filter(f, d.keys())
        
    if m != []:
        return (m[0], d[m[0]])
    return None

def find(f, seq):
    """Return first item in sequence where f(item) == True."""
    for item in seq:
        if f(item): 
            return item

