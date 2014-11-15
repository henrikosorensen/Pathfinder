from util import *
import supybot.utils as utils
import hlimport
import character

MaximumXMLSize = 16777216

class GameState(object):
    def __init__(self):
        self.combatRound = -1
        self.characters = []
        self.initOrder = []
        self.effectDurations = []

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
        return subStringMatchItemInList(self.characters, "name", charname)

    def getChars(self, charname):
        chars = []
        if charname == 'party':
            chars = self.getPartyMembers()
        else:
            c = self.getChar(charname)
            if c is not None:
                chars = [c]
        return chars
   
    def getStat(self, charname, stat):
        c = self.getChar(charname)
        if c is None:
            return None
        
        stat = subStringMatchDictKey(c.stats, stat)
        if stat is None:
            return None
        return stat + (c,)

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
        expired = filter(f, self.effectDurations)

        for e in expired:
            self.effectDurations.remove(e)

        return expired

    def getPartyMembers(self):
        party = [] 
        for char in self.characters:
            if char.partyMember:
                party.append(char)
        return party

    def hlImport(self, url, partyMembers):
        hlXml = utils.web.getUrl(url, MaximumXMLSize)
        chars = hlimport.importCharacters(hlXml)

        count = 0
        for c in chars:
            oldChar = self.getChar(c.name)
            if oldChar is not None:
                self.characters.remove(oldChar)

            self.characters.append(c)
            c.partyMember = partyMembers
            count += 1

        return count

    def __sortInitiativeOrder(self):
        # sort descendingly by tatal initiative, then modifier
        self.initOrder = sorted(self.initOrder, key = lambda k: k.get('initiative'), reverse=True)
        self.initOrder = sorted(self.initOrder, key = lambda k: k.get('initiative roll'), reverse=True)
        return self.initOrder

    def initOrderRemove(self, charname):
        c = self.getChar(charname)
        if c in self.initOrder:
            self.initOrder.remove(c)
            return c
        return None
            
    def initOrderSet(self, c, initiative, roll):
        # don't overwrite imported char's initiative modifier
        if c.temporary:
            c.set("initiative", initiative)

        c.set("initiative roll", roll)
        
        # If not in order already, add c
        if c not in self.initOrder:
            self.initOrder.append(c)
        
        # Resort iniitOrder
        self.__sortInitiativeOrder();

    def durationEffectAdd(self, name, duration):
        e = { "name": name, "length": duration, "startRound": self.combatRound }
        self.effectDurations.append(e)

    def swap(self, c1, c2):
        party = c1 if c1.partyMember else c2
        nonParty = c1 if not c1.partyMember else c2
        
        damage = party.get("totalhp") - party.get("hp")
        newHp = nonParty.get("totalhp") - damage
        nonParty.set("hp", newHp)

        for i in range(0, len(nonParty.dailyUse)):
            if nonParty.dailyUse[i]["name"] == party.dailyUse[i]["name"]:
                nonParty.dailyUse[i]["used"] = party.dailyUse[i]["used"]
            else:
                assert(False)

        nonParty.partyMember = True
        party.partyMember = False