from util import *

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
        self.stats = { 
            "name": self.name,
            "attacks": self.attacks,
            "spells": self.spells
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
