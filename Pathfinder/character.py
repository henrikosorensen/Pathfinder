from .util import *
from . import item

class Character(object):
    def __init__(self, name):
        self.name = name;
        self.attacks = []
        self.spells = []
        self.player = None
        self.temporary = False
        self.partyMember = False
        self.skills = []
        self.classes = []
        self.dailyUse = []
        self.inventory = item.Inventory()
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
        if isinstance(value, str):
            if value.isdigit():
                if value.find(".") == -1:
                    value = int(value)
                else:
                    value = float(value)

        self.stats[key.lower()] = value

    def get(self, key):
        return self.stats.get(key.lower())

    def __getitem__(self, item):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return None

    def getSpell(self, name):
        return subStringMatchItemInList(self.spells, "name", name)

    def getAttack(self, name):
        return subStringMatchItemInList(self.attacks, "name", name)

    def getDailyUseAbility(self, name):
        return subStringMatchItemInList(self.dailyUse, "name", name)

    def useDailyAbility(self, ability, uses):
        du = self.getDailyUseAbility(ability)
        if du:
            du["used"] += uses

        return du
    
    def cast(self, spell, levelAdjustment):
        # If spell is spontaneously cast and above level 0, do some accounting
        if spell.get("spontaneous") and spell.get("spontaneous").lower() == "yes" and spell["level"] > 0:
            # Character COULD have multiply spontaneous caster classes, find out which one we have to add to cast count
            spellUses = subStringMatchItemsInList(self.dailyUse, "name", "Level %d" % (spell["level"] + levelAdjustment))
            for sc in spellUses:
                # if spell's caster class matches spellUses class, increment uses.
                spellClass = spell["class"].lower()
                spellUsesClass = sc["class"].lower()
                if spellUsesClass.find(spellClass) != -1:
                    sc["used"] += 1
                    return sc

        return None

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

