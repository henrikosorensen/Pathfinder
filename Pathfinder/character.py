if __package__ != '':
    from .util import *
    from . import item
else:
    from util import *
    import item


import re

class Character(object):
    def __init__(self, name):
        self.name = name;
        self.attacks = {}
        self.spells = {}
        self.player = None
        self.temporary = False
        self.partyMember = False
        self.skills = {}
        self.classes = {}
        self.trackedResources = {}
        self.inventory = item.Inventory()
        self.spellCaster = {}
        self.stats = {}

    def set(self, key, value):
        # if value is a string containing a number, convert it to int or float first
        value = tryToConvertValue(value)

        self.stats[key.lower()] = value

    def get(self, key):
        return self.stats.get(key.lower())

    def __getitem__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return None

    def getSpell(self, name, level):
        for caster in self.spellCaster.values():
            found = caster.getSpell(name, level)
            if found is not None:
                return caster, found

        return None, None

    def getAttack(self, name):
        a = subStringMatchDictKey(self.attacks, name)
        return a

    def getTrackedResource(self, name):
        return subStringMatchDictKey(self.trackedResources, name)

    def addToInventory(self, i):
        return self.inventory.add(i)

    def getInventoryItem(self, name):
        return self.inventory.search(name)

    def removeFromInventory(self, i):
        return self.inventory.remove(i)

    def getStat(self, statName):
        f = lambda s: subStringMatch(s, statName)
        stat = findBest(f, subStringMatchQuality, self.stats.keys())
        if stat is None:
            return None

        return stat, self.stats[stat]

    def searchStats(self, stat):
        stat = stat.lower()
        match = lambda s: s.find(stat) > -1
        return list(filter(match, self.stats.keys()))

    def rest(self):
        for r in self.trackedResources.values():
            r.dailyReset()

        for caster in self.spellCaster.values():
            caster.resetSpellUsage()



def abilityBonus(score):
    return (score - 10) / 2

class Class(object):
    def __init__(self, name, level, archetypes = []):
        self.level = level
        self.name = name
        self.archetypes = archetypes

    @staticmethod
    def initFromHl(name, level):
        # Class Name (Archetypes)
        m = re.match("(\w+)(?: \((.+)\))?", name)

        if m is None:
            raise RuntimeError("Couldn't untangle class name {}".format(name))

        name = m.group(1)
        archetypes = m.group(2).split(',') if m.group(2) is not None and m.group(2) != '' else []

        return Class(name, level, archetypes)

    def isSameClass(self, className):
        return className.lower().split('(')[0].strip() == self.name.lower().strip()

    def getLongName(self):
        if self.archetypes == []:
            return self.name
        else:
            return "{} ({})".format(self.name, ', '.join(self.archetypes))

    def __eq__(self, other):
        self.isSameClass(other.name)


class TrackedResource(object):
    def __init__(self, name, used, max, daily):
        self.name = name
        self.used = used
        self.max = max
        self.perDay = daily

    def dailyReset(self):
        if self.perDay:
            self.used = 0

    def use(self, amount = 1):
        if self.used + amount <= self.max and self.used + amount >= 0:
            self.used += amount
            return True
        else:
            return False

    def __str__(self):
        return '{} {}/{}{}'.format(self.name, self.used, self.max, " per day" if self.perDay else "")
