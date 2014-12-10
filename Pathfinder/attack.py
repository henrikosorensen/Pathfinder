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

    def roll(self, roller):
        return roller.doRoll("d20")

    def doDamageRoll(self, roller, damageAdjustment, crit):
        damage = 0
        trace = ""

        multiplier = 1 if not crit else self.criticalMultiplier

        for i in range(0, multiplier):
            roll = self.damageRoll
            if damageAdjustment != 0:
                roll += " + %d" % (damageAdjustment)

            damageRoll = roller.doRoll(roll)
            damage += damageRoll[0]
            trace += damageRoll[1]

        return {
            "damage": damage,
            "damageTrace": trace
        }

    def doAttackRoll(self, roller, attackAdjustment, attackNumber, ac, damageAdjustment):
        roll= self.roll(roller)[0]
        bonus = self.bonus[attackNumber] + attackAdjustment

        attackRoll = {
            "roll" : roll,
            "bonus" : bonus,
            "total" : roll + bonus,
            "trace" : "%d %s %d" % (roll, '+' if bonus >= 0 else '-', bonus),
            "hit" : None
        }

        if ac is not None:
            # Check if attack hits
            attackRoll["hit"] = attackRoll["total"] >= ac or roll == 20

            # is it a crit as well?
            potentialCrit = attackRoll["hit"] and roll >= self.criticalRange
            if potentialCrit:
                critConfirmation = self.doAttackRoll(roller, attackAdjustment, attackNumber, ac)
                attackRoll["critical"] = critConfirmation["hit"]
            else:
                attackRoll["critical"] = False

            # Do a damage roll as well if it hits.
            if attackRoll["hit"]:
                damageRoll = self.doDamageRoll(roller, damageAdjustment, attackRoll["critical"])
                attackRoll.update(damageRoll)


        return attackRoll

    def getDescription(self):
        crit = "20/x%d" % (self.criticalMultiplier)

        if self.criticalRange < 20:
            crit = str(self.criticalRange) + '-' + crit

        bonus = map(plusPrefix, self.bonus)
        bonus = string.join(bonus, "/")

        return "%s %s %s" % (self.name, bonus, crit)

    def __str__(self):
        return self.getDescription()

    def getFullAttackCount(self):
        return len(self.bonus)


critXp = re.compile("(?:(\d{2})-\d{2}/)?[\xd72x](\d+)")

def attackBonus(b):
    if type(b) is int:
        return [b]
    else:
        bonuses = b.split('/')
        # Hero lab likes to stick an x2 on double natural attacks' bonuses, so only run int on the stuff before the any space.
        return map(lambda bonus: int(bonus.split()[0]), bonuses)

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


def createFromHeroLab(attack):
    a = Attack(attack["name"])
    a.bonus = attackBonus(attack["attack"])
    a.damageText = attack["damage"]
    a.damageRoll = getDamageRoll(attack["damage"])
    a.quantity = attack.get("quantity")

    critRange = critical(attack["crit"])
    a.criticalRange = critRange[0]
    a.criticalMultiplier = critRange[1]

    a.category = attack.get("category")
    a.equipped = attack.get("equipped")
    a.damageType = attack.get("typetext")

    return a
