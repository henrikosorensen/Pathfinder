import string
import re

def plusPrefix(n):
    if n >= 0:
        return "+%d" %n
    else:
        return str(n)

class Attack(object):
    def __init__(self, name):
        self.name = name
        self.bonus = []
        self.criticalRange = 20
        self.criticalMultiplier = 2
        self.quantity = 1
        self.damageText = ""
        self.damageRoll = ""
        self.damageType = ""
        self.category = ""
        self.equipped = ""

    def __getitem__(self, item):
        return self.__dict__[item]

    def getDescription(self):
        crit = "20/x%d" % (self.criticalMultiplier)

        if self.criticalRange < 20:
            crit = str(self.criticalRange) + '-' + crit

        bonus = map(plusPrefix, self.bonus)
        bonus = '/'.join(bonus)

        return "%s %s %s %s" % (self.name, bonus, self.damageText, crit)

    def __str__(self):
        return self.getDescription()

    def getFullAttackCount(self):
        return len(self.bonus)

    def inCritRange(self, roll):
        return roll >= self.criticalRange


critXp = re.compile("(?:(\d{2})-\d{2}/)?[\xd72x](\d+)")

def attackBonus(b):
    if type(b) is int:
        return [b]
    else:
        bonuses = b.split('/')
        # Hero lab likes to stick an x2 on double natural attacks' bonuses, so only run int on the stuff before the any space.
        #return list(map(lambda bonus: int(bonus.split()[0]), bonuses))
        return [int(bonus.split()[0]) for bonus in bonuses]


def getDamageRoll(roll):
    return roll.split(' ')[0]

def critical(crit):
    match = critXp.match(crit)
    if match:
        minRoll = int(match.group(1)) if match.group(1) else 20
        multiplier = int(match.group(2)) if match.group(2) else 2
        return (minRoll, multiplier)
    else:
        raise Exception("Couldn't find critical range in %s" % crit)
