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
        self.stats = { 
            "name": self.name,
            "attacks": self.attacks,
            "spells": self.spells,
            "classes": self.classes,
            "skills": self.skills,
            "dailyUse": self.dailyUse,
            "inventory": self.inventory
        }


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
        return subStringMatchDictKey(self.attacks, name)

    def getDailyUseAbility(self, name):
        return subStringMatchDictKey(self.dailyUse, name)

    def useDailyAbility(self, ability, uses):
        du = self.getDailyUseAbility(ability)
        if du:
            du["used"] += uses

        return du

    def addToInventory(self, i):
        return self.inventory.add(i)

    def getInventoryItem(self, name):
        return self.inventory.search(name)

    def removeFromInventory(self, i):
        return self.inventory(i)

    def getStat(self, statName):
        match = subStringMatchDictKey(self.stats, statName)
        if match is None:
            return None
        return match + (self,)

    def rangedTouchAttackBonus(self):
        return self.stats["base attack bonus"] + self.stats["dexterity bonus"]

    def touchAttackBonus(self):
        return self.stats["base attack bonus"] + self.stats["strength bonus"]

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


