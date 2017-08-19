if __package__ != '':
    from .util import *
    from . import hlimport
    from . import character
else:
    from util import *
    import hlimport
    import character

import enum

class Ruleset(enum.Enum):
    Pathfinder = "Pathfinder"
    FifthEdition = "D&D 5th Edition"


class GameState(object):
    def __init__(self):
        self.combatRound = -1
        self.characters = []
        self.initOrder = []
        self.effectDurations = []
        self.ruleset = Ruleset.Pathfinder

    def inCombat(self):
        return self.combatRound > 0

    def beginCombat(self):
        self.combatRound = 1
        self.initOrder = []
        self.effectDurations = []

    def endCombat(self):
        if self.inCombat():
            self.combatRound = -1
            self.initOrder = []
            self.__cullTempCharacters()

    def getRound(self):
        return self.combatRound
    
    def nextRound(self):
        self.combatRound += 1
        return self.__durationChecker()

    def prevRound(self):
        if self.combatRound > 1:
            self.combatRound -= 1

    def getChar(self, charname):
        return find(lambda c: c.name == charname, self.characters)

    def findChar(self, charname):
        return subStringMatchItemInList(self.characters, "name", charname)

    def findChars(self, charname):
        chars = []
        if charname == 'party':
            chars = self.getPartyMembers()
        else:
            c = self.findChar(charname)
            if c is not None:
                chars = [c]
        return chars

    def newCharacter(self, name, temp):
        c = character.Character(name)
        c.temporary = temp
        self.characters.append(c)
        return c

    def __cullTempCharacters(self):
        chars = []
        for c in self.characters:
            if not c.temporary:
                chars.append(c)
        
        self.characters = chars

    def __durationChecker(self):
        f = lambda e : self.combatRound >= e["startRound"] + e["length"]
        expired = list(filter(f, self.effectDurations))

        for e in expired:
            self.effectDurations.remove(e)

        return expired

    def getPartyMembers(self):
        party = [] 
        for char in self.characters:
            if char.partyMember:
                party.append(char)
        return party

    def hlImport(self, db, hlXml, partyMembers):
        if self.ruleset == Ruleset.Pathfinder:
            hlimporter = hlimport.HeroLabPfImporter()
        elif self.ruleset == Ruleset.FifthEdition:
            hlimporter = hlimport.HeroLab5eImporter()

        chars = hlimporter.importCharacters(hlXml)

        count = 0
        for c in chars:
            oldChar = self.getChar(c.name)
            if oldChar is not None:
                self.removeCharacter(oldChar)

            self.characters.append(c)
            c.partyMember = partyMembers
            count += 1

        return count

    def __sortInitiativeOrder(self):
        # sort descendingly by tatal initiative, then modifier
        self.initOrder = sorted(self.initOrder, key = lambda k: k.get('initiative'), reverse=True)
        self.initOrder = sorted(self.initOrder, key = lambda k: k.get('initiative roll'), reverse=True)
        return self.initOrder

    def initOrderRemove(self, c):
        if c in self.initOrder:
            self.initOrder.remove(c)
            return True
        return False

    def removeCharacter(self, c):
        self.initOrderRemove(c)
        self.characters.remove(c)
        return True

    def initOrderSet(self, c, initiative, roll):
        # don't overwrite imported char's initiative modifier
        if c.temporary:
            c.set("initiative", initiative)

        c.set("initiative roll", roll)
        
        # If not in order already, add c
        if c not in self.initOrder:
            self.initOrder.append(c)
        
        # Resort iniitOrder
        self.__sortInitiativeOrder()

    def durationEffectAdd(self, name, duration):
        e = {"name": name, "length": duration, "startRound": self.combatRound}
        self.effectDurations.append(e)

    def getDurationEffect(self, name):
        return subStringMatchItemInList(self.effectDurations, "name", name)

    def removeDurationEffect(self, e):
        self.effectDurations.remove(e)

    def swap(self, c1, c2):
        party = c1 if c1.partyMember else c2
        nonParty = c1 if not c1.partyMember else c2
        
        damage = party.get("totalhp") - party.get("hp")
        newHp = nonParty.get("totalhp") - damage
        nonParty.set("hp", newHp)

        for ability in party.trackedResources.keys():
            if ability in nonParty.trackedResources:
                nonParty.trackedResources[ability].used = party.trackedResources[ability].used

        nonParty.partyMember = True
        party.partyMember = False
