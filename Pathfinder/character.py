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
        self.dailyUse = {}
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
        key, a = subStringMatchDictKey(self.attacks, name)
        return a

    def getDailyUseAbility(self, name):
        return subStringMatchDictKey(self.dailyUse, name)

    def useDailyAbility(self, ability, uses):
        ability, du = self.getDailyUseAbility(ability)
        if du:
            du["used"] += uses

        return du

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
        return

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


