###
# coding: utf-8
# Copyright (c) 2014, Henrik Sørensen
# All rights reserved.
#
#
###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.conf as conf
import random
import re
import hlimport
import sys
from operator import itemgetter
from character import Character
#import json
import jsonpickle

MaximumXMLSize = 16777216

def find(f, seq):
    """Return first item in sequence where f(item) == True."""
    for item in seq:
        if f(item): 
            return item

class PfState(object):
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
        return self.subStringMatchItemInList(self.characters, "name", charname)

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
        
        return self.subStringMatchDictKey(c.stats, stat)

    def setStat(self, c, stat, value):
        c.set(stat, value)

    def subStringMatchItemsInList(self, l, key, subString):
        f = lambda item : item[key].lower().find(subString.lower()) > -1
        return filter(f, l)        

    def subStringMatchItemInList(self, l, key, subString):
        m = self.subStringMatchItemsInList(l, key, subString)
        if m != []:
            return m[0]
        else:
            return None

    def subStringMatchDictKey(self, d, subString):
        f = lambda k : k.lower().find(subString.lower()) > -1
        m = filter(f, d.keys())
        
        if m != []:
            return (m[0], d[m[0]])

    def newCharacter(self, name, temp):
        c = Character(name)
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

    def pickle(self, path):
        pickle.dump(self, open(path, "wb"))

    def swap(self, c1, c2):
        party = c1 if c1.partyMember else c2
        nonParty = c1 if not c1.partyMember else c2
        
        damage = party.get("totalhp") - party.get("hp")
        newHp = nonParty.get("totalhp") - damage
        nonParty.set("hp", newHp)
        
        nonParty.partyMember = True
        party.partyMember = False
       


class Pathfinder(callbacks.Plugin):
    """Add the help for "@plugin help Pathfinder" here
    This should describe *how* to use this plugin."""
    def __init__(self, irc):
        self.__parent = super(Pathfinder, self)
        self.__parent.__init__(irc)
        self.rng = random.Random()   # create our rng
        self.rng.seed()   # automatically seeds with current time

        self.numberExp = re.compile("^\d+$")
        self.diceExp = re.compile("^(\d{0,2})d([1-9][0-9]{0,2})\s*([+\-]?)\s*(\d*)$")
        self.charStatExp = re.compile("^(\w+)\s+([\w ]+)$")
        
        self.dataFile = conf.supybot.directories.data.dirize("PathFinderState.json")
        self.gameState = self.resumeState(self.dataFile)
        
    def die(self):
        self.saveState(self.dataFile)

    def flush(self):
        self.saveState(self.dataFile)

    def resumeState(self, filename):
        gameState = PfState()
        try:
            f = file(filename)
            data = f.readline()
            f.close()
            gameState = jsonpickle.decode(data)
        except Exception, e:
            self.log.warning('Couldn\'t load gamestate: %s', e.message)

        return gameState

    def saveState(self, filename):
        try:
            f = utils.file.AtomicFile(filename)
            #json.dump(self.gameState.getDataDict(), f, indent=4)
            data = jsonpickle.encode(self.gameState)
            f.write(data)
            f.close()
        except Exception, e:
            self.log.warning('Couldn\'t save gamestate: %s', e.message)
            f.rollback()

#    def save(self, irc, msg, args):
#        self.saveState(self.dataFile)
#    save = wrap(save)


    def __matchDice(self, s):
        # Did we get fed a pure integer?
        m = self.numberExp.match(s)
        if m:
            return (1, int(m.group(0)), 0, "int")

        # Try to see if it's a dice expression
        m = self.diceExp.match(s)
        if m:
            dice = int(m.group(1)) if m.group(1) else 1
            sides = int(m.group(2))
            adjustment = int(m.group(4)) if m.group(4) else 0
            if m.group(3) == '-':
                adjustment = -adjustment
            return (dice, sides, adjustment, "dice")
        else:
            return None

    def __rollResultString(self, dice, sides, adjustment, result):
        if dice == 1 and not adjustment:
            return "d%d roll: %d" % (sides, result[0])
        else:
            a = ""
            if adjustment:
                if adjustment > 0:
                    a = " + %d" % adjustment
                else:
                    a = " - %d" % -adjustment

            return "%dd%d%s roll %s totals %d" % (dice, sides, a, result[1], result[0])

    def __roll(self, dice, sides, adjustment):
        rolls = []
        total = 0

        for x in range(0, dice):
            roll = random.randrange(1, sides)
            rolls.append(roll)
            total += roll

        if adjustment:
            total += adjustment

        return (total, rolls)

    def __doRoll(self, dice, sides, adjustment):
        return self.__rollResultString(dice, sides, adjustment, self.__roll(dice, sides, adjustment))


    def __doStatRoll(self, irc, charname, statName):
        chars = self.gameState.getChars(charname)

        if chars == []:
            irc.reply("Unknown character")
            return

        for c in chars:
            stat = self.gameState.getStat(c.name, statName)
            if stat is None:
                irc.reply("Unknown stat on %s. " % c.name)
            else:
                try:
                    statValue = int(stat[1])
                    realName = stat[0]
                    roll = self.__roll(1, 20, statValue)
                    irc.reply("%s's %s roll is %d + %d = %d" % (c.name, realName, roll[1][0], statValue, roll[0]))
                except:
                    irc.reply("%s is not a numeric stat" % realName)
        

    def roll(self, irc, msg, args, text):
        """
        usage <die sides>, <number of dice>d<die sides> or <number of dice>d<die sides> + <number>
        """
        text = text.strip()

        diceMatch = self.__matchDice(text)
        statMatch = self.charStatExp.match(text)
        if diceMatch:
            irc.reply(self.__doRoll(diceMatch[0], diceMatch[1], diceMatch[2]))
        elif statMatch:
            self.__doStatRoll(irc, statMatch.group(1), statMatch.group(2))
        else:
            irc.reply("Not understood.")
        
    roll = wrap(roll, ["text"])

    def begincombat(self, irc, msg, args, user):
        """starts combat session"""
        self.gameState.beginCombat()
        irc.reply("Party is in combat, roll initiative.")
    begincombat = wrap(begincombat, ["public", "user"])

    def endcombat(self, irc, msg, args, user):
        """ends combat session"""
        if self.gameState.inCombat():
            self.gameState.endCombat()
            irc.reply("Party's fight is complete.")
        else:
            irc.reply("Party isn't in combat.")            

    endcombat = wrap(endcombat, ["public", "user"])

    def nextround(self, irc, msg, args, user):
        """starts next combat round"""
        if self.gameState.inCombat():
            expired = self.gameState.nextRound()
            irc.reply("Combat round %d." % self.gameState.getRound())
            
            for e in expired:
                irc.reply("%s has expired." % e["name"])
        else:
            irc.reply("Party isn't in combat.")

    nextround = wrap(nextround, ["public", "user"])

    def prevround(self, irc, msg, args, user):
        """resumes previous combat round"""
        if self.gameState.inCombat():
            if self.gameState.getRound == 1:
                irc.reply("This is the first round of combat.")
            else:
                self.gameState.prevRound()
                irc.reply("Combat round %d.")
        else:
            irc.reply("Party isn't in combat.")

    prevround = wrap(prevround, ["public", "user"])

    def round(self, irc, msg, args, user):
        """outputs current combat round"""
        if not self.gameState.inCombat():
            irc.reply("Party isn't in combat.")
        else:
            irc.reply("This is combat round %d." % self.gameState.getRound())
    round = wrap(round, ["user"])

    def party(self, irc, msg, args, url):
        """list known party members"""
        party = self.gameState.getPartyMembers()
        
        s = ""
        if party == []:
            s = "Party is empty."
        else:
            s = "Party members are: "
            for c in party:
                s += "%s, " % c.name 
            s = s[:-2]

        irc.reply(s)
    party = wrap(party, ["user"])


    def partymember(self, irc, msg, args, user, charname, member):
        """ get or set party membership on character """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return 
    
        if member is None:
            irc.reply("%s is%s a party member" % (c.name, "" if c.partyMember else " not"))
        else:
            c.partyMember = member
            irc.reply("%s is now%s a party member" % (c.name, "" if c.partyMember else " not"))
    partymember = wrap(partymember, ["user", "anything", optional("boolean")])

    def hlimportcharacters(self, irc, msg, args, url, partyMembers):
        """<url> <are party members bool> - import character data from exported Hero Lab characters in XML """
        try:
            count = self.gameState.hlImport(url, partyMembers)
            irc.reply("%d characters imported" % count)
        except Exception, e:
            irc.reply("Import failed: %s" % e.message)

    hlimportcharacters = wrap(hlimportcharacters, ["private", "admin", "url", optional("boolean")])

    def listcharacters(self, irc, msg, args, user):
        """lists known character"""
        s = ""
        if self.gameState.characters != []:
            for c in self.gameState.characters:
                s += c.name + ", "
            irc.reply(s[:-2]) # skips trailing ', '
        else:
            irc.reply("Character list is empty")

    listcharacters = wrap(listcharacters, ["user"])

    def getstat(self, irc, msg, args, charname, stat):
        """get stat on given character"""
        st = self.gameState.getStat(charname, stat)
        statName = st[0]
        value = st[1]
        if value is None:
            irc.reply("Character or stat is unknown.")
        else:
            irc.reply("%s's %s is %s" % (charname, statName, value))
    getstat = wrap(getstat, ["anything", "text"])

    def setstat(self, irc, msg, args, charname, stat, value):
        """sets stat on character to the given value"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
        else:
    
            irc.reply("%s's %s is now %s" % (c.name, stat, value))

    setstat = wrap(setstat, ["anything", "anything", "anything"])

    def liststats(self, irc, msg, args, charname):
        """lists known stats on a character, must be used in private message"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
        else:
            irc.reply(c.stats)
    liststats = wrap(liststats, ["private", "anything"])

    def __getHP(self, name):
        c = self.gameState.getChar(name)
        if c is None:
            return None
        hp = c.get("hp")
        totalhp = c.get("totalhp")
        if totalhp is None:
            return "-%d " % hp
        else:
            return "%d/%d" % (hp, totalhp)

    def hp(self, irc, msg, args, charname):
        """lists of a character if given a name, or every known character"""
        s = ""
        if charname is not None:
            s = "%s %s" % (charname, self.__getHP(charname))
        else:
            for c in self.gameState.characters:
                s += "%s %s, " % (c.name, self.__getHP(c.name))
            if s == "":
                s = "No characters found."
            else:
                s = s[:-2]

        irc.reply(s)
    hp = wrap(hp, [optional("something")])

    def __adjustHP(self, irc, c, text, isDamage):
        diceMatch = self.__matchDice(text)
        if diceMatch is None:
            irc.reply("Invalid value.")
            return
        elif diceMatch[3] == "int":
            adjustment = diceMatch[1]
        else:
            adjustment = self.__roll(diceMatch[0], diceMatch[1], diceMatch[2])[0]

        hp = c.get("hp")
        totalhp = c.get("totalhp")
        s = c.name                
        
        if isDamage:
            hp -= adjustment
            s += " is damaged for %d" % adjustment
        else:
            hp += adjustment
            # avoid hp overflow on heals
            if totalhp is not None and hp > totalhp:
                hp = totalhp
                s += " is healed for %d" % adjustment            

        c.set("hp", hp)

        if totalhp is None:
            irc.reply("%s is now: %d hp." % (s, hp))
        else:
            irc.reply("%s is now: %d/%d hp." % (s, hp, totalhp))


    def heal(self, irc, msg, args, user, charname, adjustment):
        """character <int> or <dice roll>"""
        chars = self.gameState.getChars(charname)
        if chars == []:
            irc.reply("Unknown character")
            return

        for c in chars:
            self.__adjustHP(irc, c, adjustment, False)
    heal = wrap(heal, ["user", "something", rest("something")])

    def damage(self, irc, msg, args, user, charname, adjustment):
        """character <int> or <dice roll>"""
        chars = self.gameState.getChars(charname)
        if chars == []:
            irc.reply("Unknown character")
            return

        for c in chars:
            self.__adjustHP(irc, c, adjustment, True)
    damage = wrap(damage, ["user", "something", rest("something")])
 
    def __getInitiativeOrderString(self):
        s = ""
        for c in self.gameState.initOrder:
            s += "%s %d, " % (c.get("name"), c.get("initiative roll"))
        if s == "":
            return "Initiative order is empty"
        else:
            return s[:-2]

    def removeinitiative(self, irc, msg, args, user, charname):
        """remove character from initiative order"""
        c = self.gameState.initOrderRemove(charname)
        if c is not None:
            irc.reply("%s removed from initiative order" % c.name)
        else:
            irc.reply("%s not in initative order" % charname)

    removeinitiative = wrap(removeinitiative, ["user", "something"])

    def __doInitiative(self, irc, char, modifier, roll):
        # No modifier and char doesn't have init modifier info, bail
        if modifier is None and char.get("initiative") is None:
            irc.reply("Please supply %s's initiative modifier." % char.name)
            return
        # No initative modifier override, use char's value
        if modifier is None:
            modifier = char.get("initiative")                        
        if roll is None:
            roll = random.randrange(1, 20)

        self.gameState.initOrderSet(char, modifier, roll + modifier)

        irc.reply("%s's initiative is %d (%d + %d)." % (char.name, roll + modifier, roll, modifier))

    def initiative(self, irc, msg, args, charname, modifier, roll):
        """lists initiative order, rolls initiative for a character, or the party as whole if given the name 'party'"""
        if not self.gameState.inCombat():
            irc.reply("Not in combat.")
            return
        # Not given any character name, just message current known order
        if charname is None:
            s = self.__getInitiativeOrderString()
            irc.reply(s)
            return

        chars = self.gameState.getChars(charname)
        # Unknown character name, create temp character.
        if chars == []:
            if charname == "party":
                irc.reply("No party members found")
                return

            c = self.gameState.newCharacter(charname, True)
            # We don't know the total hitpoint poll of temp chars
            c.set("hp", 0)
                    
            chars = [c]
        
        for c in chars:
            self.__doInitiative(irc, c, modifier, roll)
    
    initiative = wrap(initiative, [optional("something"), optional("int"), optional("int")])
            

    def duration(self, irc, msg, args, user, rounds, effect):
        """ <duration in rounds of effect> <effect string>"""
        if self.gameState.inCombat():
            self.gameState.durationEffectAdd(effect, rounds)
            irc.reply("%s for %d rounds." % (effect, rounds))
        else:
            irc.reply("Not in combat")
    duration = wrap(duration, ["user","int", "text"])

    def listspells(self, irc, msg, args, user, charname):
        """list known spells on given character"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
            return
        if c.spells == []:
            irc.reply("%s has no spells" % c.name)
        else:
            s = "%s spells are: " % c.name
            for spell in c.spells:
                s += spell["name"] + ", "
            irc.reply(s[:-2])

    listspells = wrap(listspells, ["user", "private", "something"])

    def spell(self, irc, msg, args, user, charname, spellname):
        """ give details on a spell """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
            return
        
        s = self.gameState.subStringMatchItemInList(c.spells, "name", spellname)
        if s is None:
            irc.reply("Unknown spell")
        else:
            irc.reply("%s level: %s casttime: %s save: %s range: %s, duration: %s" % (s["name"], s["level"], s["casttime"], s["save"], s["range"], s["duration"]))

    spell = wrap(spell, ["user", "something", rest("text")])

    def listattacks(self, irc, msg, args, user, charname):
        """lists known attacks on given character"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")

        if c.attacks == []:
            irc.reply("%s has no attacks" % c.name)
        else:
            s = "%s's attacks are: " % c.name
            for attack in c.attacks:
                s += "%s, " % (attack["name"])
            irc.reply(s[:-2])
    listattacks = wrap(listattacks, ["user", "private", "something"])

    def attack(self, irc, msg, args, user, charname, attackName, adjustment):
        """ give details on an attack """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return 

        a = self.gameState.subStringMatchItemInList(c.attacks, "name", attackName)
        if a is None:
            irc.reply("No attack by that name.")
            return 
        else:
            s = "'%s' bonus: %s damage: %s crit: %s" % (a["name"], a["bonus"], a["damage"], a["critical"])
            irc.reply(s.encode("utf-8"))
    
    attack = wrap(attack, ["user", "something", "something", optional("int")])


    def swap(self, irc, msg, args, user, char1, char2):
        """<char 1> <char 2> transfers damage and party membership between them"""
        c1 = self.gameState.getChar(char1)
        c2 = self.gameState.getChar(char2)
        if c1 is None:
            irc.reply("%s unknown character." % char1)
        elif c2 is None:
            irc.reply("%s unknown character." % char2)
        elif c1.partyMember ^ c2.partyMember == True:
            self.gameState.swap(c1, c2)
            irc.reply("Characters swapped %s is now the active party member" % (c1.name if c1.partyMember else c2.name))
        elif c1.partyMember and c2.partyMember:
            irc.reply("Cannot swap two party members")
        else:
            irc.reply("Cannot swap two non-party members")
            
    swap = wrap(swap, ["user", "somethingWithoutSpaces", "somethingWithoutSpaces"])

Class = Pathfinder


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
