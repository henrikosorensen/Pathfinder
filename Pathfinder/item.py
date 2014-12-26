from util import *

class Item(object):
    def __init__(self, name, quantity = 1, weight = 0, value = 0):
        self.name = name
        self.quantity = quantity
        self.weight = weight
        self.value = value

    def __str__(self):
        return "%dx %s %.2f lbs." % (self.quantity, self.name, self.weight)

    def shortString(self):
        if self.quantity != 1:
            return "%d %s" % (self.quantity, self.name)
        else:
            return self.name

class Inventory(object):
    def __init__(self):
        self.items = {}

    def add(self, i):
        if self.get(i.name) is None:
            self.items[i.name] = i
        else:
            j = self.get(i.name)
            j.quantity += i.quantity
            j.value = i.value
            j.weight = i.weight

    def remove(self, i):
        try:
            del self.items[i.name]
            return True
        except KeyError:
            return False

    def quantityAdjustItem(self, i, adjustment):
        if i.quantity - adjustment < 1:
            self.remove(i)

        i.quantity += adjustment

        return i

    def get(self, name):
        return self.items.get(name)

    def search(self, name):
        return subStringMatchDictKey(self.items, name)[1]

    def getItems(self):
        return self.items

    def getTotalValue(self):
        value = 0
        for name, i in self.items.items():
            value += i.value * i.quantity

        return value

    def getTotalWeight(self):
        weight = 0
        for name, i in self.items.items():
            weight += i.weight * i.quantity

        return weight

    def __str__(self):
        items = map(lambda i: i.shortString(), self.items.values())
        return ", ".join(items)
