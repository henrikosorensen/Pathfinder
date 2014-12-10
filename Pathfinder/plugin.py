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
from operator import itemgetter
from util import *
import item
import gamestate
import jsonpickle
import rollArgs
import string
import random
import re
import sys

MaximumXMLSize = 16777216

class Pathfinder(callbacks.Plugin):
    """Add the help for "@plugin help Pathfinder" here
    This should describe *how* to use this plugin."""

    def __init__(self, irc):
        self.__parent = super(Pathfinder, self)
        self.__parent.__init__(irc)
        self.rng = random.Random()   # create our rng
        self.rng.seed()   # automatically seeds with current time

        self.dataFile = conf.supybot.directories.data.dirize("PathFinderState.json")
        self.gameState = self.resumeState(self.dataFile)

        self.roller = rollArgs.Roller(self.gameState, self.rng)
        self.partyRegExp = re.compile("^party ")
        
    def die(self):
        self.saveState(self.dataFile)

    def flush(self):
        print "Pathfinder flushing."
        self.saveState(self.dataFile)

    def resumeState(self, filename):
        gameState = gamestate.GameState()
        try:
            f = file(filename)
            data = f.readline()
            f.close()
            gameState = jsonpickle.decode(data)
        except Exception as e:
            self.log.warning('Couldn\'t load gamestate: %s', e.message)

        return gameState

    def saveState(self, filename):
        try:
            f = utils.file.AtomicFile(filename)
            #json.dump(self.gameState.getDataDict(), f, indent=4)
            data = jsonpickle.encode(self.gameState)
            f.write(data)
            f.close()
        except Exception as e:
            self.log.warning('Couldn\'t save gamestate: %s', e.message)
            f.rollback()

    def __doRoll(self, text):
        p = self.roller.parseRoll(text)
        r = self.roller.execute(p)

        return self.__rollResultString(r)

    def savegamestate(self, irc, msg, args):
        self.saveState(self.dataFile)
        irc.reply("Gamestate saved.")

    savegamestate = wrap(savegamestate, ["private", "admin"])

    def __rollResultString(self, returnValue):
        result = returnValue[0]
        trace = returnValue[1]
        s = trace

        if type(result) is bool:
            s += ": %s" % ("Success" if result else "Failure")
        else:
            s += " total %s" % result

        return s

    def roll(self, irc, msg, args, text):
        """
        usage <die sides>, <number of dice>d<die sides> or <number of dice>d<die sides> + <number>
        """
        rolls = []
        if self.partyRegExp.search(text):
            for c in self.gameState.getPartyMembers():
                rolls.append(self.partyRegExp.sub(c.name + " ", text))
        else:
            rolls.append(text)

        try:
            for roll in rolls:
                s = self.__doRoll(roll)
                irc.reply(s)
        except Exception as e:
            irc.reply("Error: " + e.__str__())

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
                irc.reply("Combat round %d." % self.gameState.getRound())
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

    def hlimport(self, irc, msg, args, url, partyMembers):
        """<url> <are party members bool> - import character data from exported Hero Lab characters in XML """
        try:
            hlXml = utils.web.getUrl(url, MaximumXMLSize)
            count = self.gameState.hlImport(hlXml, partyMembers == True)
            irc.reply("%d characters imported" % count)
        except Exception as e:
            irc.reply("Import failed: %s" % e.message)

    hlimport = wrap(hlimport, ["private", "admin", "url", optional("boolean")])

    def characters(self, irc, msg, args, user):
        """lists known characters"""
        s = ""
        if self.gameState.characters != []:
            for c in self.gameState.characters:
                s += c.name + ", "
            irc.reply(s[:-2]) # skips trailing ', '
        else:
            irc.reply("Character list is empty")

    characters = wrap(characters, ["user"])

    def __getStatString(self, char, statName):
        st = char.getStat(statName)
        if st is None:
            return "Unknown stat %s on %s" % (statName, char.name)
        else:
            return "%s's %s is %s" % (char.name, st[0], st[1])


    def getstat(self, irc, msg, args, charname, stat):
        """get stat on given character"""
        chars = self.gameState.getChars(charname)
        if chars == []:
            irc.reply("Unknown character %s" % charname)
        else:
            for c in chars:
                irc.reply(self.__getStatString(c, stat))

    getstat = wrap(getstat, ["anything", "text"])

    def setstat(self, irc, msg, args, charname, stat, value):
        """sets stat on character to the given value"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
        else:
            c.set(stat, value)
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
            return "%d " % hp
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
    hp = wrap(hp, [optional("anything")])

    def __adjustHP(self, irc, c, text, isDamage):
        adjustment = 0
        trace = []
        try:
            retVal = self.roller.doRoll(text)
            adjustment = retVal[0]
            trace = string.join(retVal[1])
        except Exception as e:
            self.log.warning(e.message)
            irc.reply("Invalid value: %s" % text)
            return

        hp = c.get("hp")
        totalhp = c.get("totalhp")
        s = c.name
        
        if isDamage:
            hp -= adjustment
        else:
            hp += adjustment
            # avoid hp overflow on heals
            if totalhp is not None and hp > totalhp:
                hp = totalhp

        s += " is %s for %d%s" % ("damaged" if isDamage else "healed", adjustment, trace)
        
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
    heal = wrap(heal, ["user", "anything", rest("anything")])

    def damage(self, irc, msg, args, user, charname, adjustment):
        """character <int> or <dice roll>"""
        chars = self.gameState.getChars(charname)
        if chars == []:
            irc.reply("Unknown character")
            return

        for c in chars:
            self.__adjustHP(irc, c, adjustment, True)
    damage = wrap(damage, ["user", "anything", rest("anything")])
 
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

    removeinitiative = wrap(removeinitiative, ["user", "anything"])

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
    
    initiative = wrap(initiative, [optional("anything"), optional("int"), optional("int")])
            

    def duration(self, irc, msg, args, user, rounds, effect):
        """ <duration in rounds of effect> <effect string>"""
        if self.gameState.inCombat():
            self.gameState.durationEffectAdd(effect, rounds)
            irc.reply("%s for %d rounds." % (effect, rounds))
        else:
            irc.reply("Not in combat")
    duration = wrap(duration, ["user", "positiveInt", "text"])

    def spells(self, irc, msg, args, user, charname):
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

    spells = wrap(spells, ["user", "private", "anything"])

    def spell(self, irc, msg, args, user, charname, spellname):
        """ give details on a spell """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
            return
        
        s = subStringMatchItemInList(c.spells, "name", spellname)
        if s is None:
            irc.reply("Unknown spell")
        else:
            irc.reply("%s level: %s casttime: %s save: %s range: %s, duration: %s" % (s["name"], s["level"], s["casttime"], s["save"], s["range"], s["duration"]))

    spell = wrap(spell, ["user", "anything", rest("text")])

    def attacks(self, irc, msg, args, user, charname):
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
    attacks = wrap(attacks, ["user", "anything"])

    def attack(self, irc, msg, args, user, charname, attackName):
        """ give details on an attack """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return 

        a = c.getAttack(attackName)
        if a is None:
            irc.reply("No attack by that name.")
            return

        irc.reply(a.getDescription())
    
    attack = wrap(attack, ["user", "anything", "anything"])

    def __getAttackRollResultString(self, c, a, roll):
        s = "%s attacks with %s: %s = %d" % (c.name, a.name, roll["trace"], roll["total"])
        if roll.get("hit") is not None:
            if roll["hit"]:
                if roll["critical"]:
                    s += " - Critical Hit!"
                else:
                    s += " - Hit!"
            else:
                s += " - Miss!"
        return s

    def __getDamageRollResultString(self, c, a, roll):
        s = "%s does %d damage with a %s: %s" % (c.name, roll["damage"], a.name, roll["damageTrace"])

        return s
    
    def __doAttackRoll(self, irc, charname, weapon, attackBonusAdjustment, ac, damageAdjustment, fullAttack):
        """<charname> <weaponname> <adjustment> <target AC>"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return
        
        a = c.getAttack(weapon)
        if a is None:
            irc.reply("No attack by that name.")
            return

        if attackBonusAdjustment is None:
            attackBonusAdjustment = 0
        if damageAdjustment is None:
            damageAdjustment = 0

        attacks = [0]
        if fullAttack:
            attacks = range(0, a.getFullAttackCount())

        for i in attacks:
            roll = a.doAttackRoll(self.roller, attackBonusAdjustment, i, ac, damageAdjustment)
            s = self.__getAttackRollResultString(c, a, roll)
            irc.reply(s)

            if roll["hit"]:
                irc.reply(self.__getDamageRollResultString(c, a, roll))

    def fullattack(self, irc, msg, args, user, charname, weapon, attackBonusAdjustment, ac, damageAdjustment):
        self.__doAttackRoll(irc, charname, weapon, attackBonusAdjustment, ac, damageAdjustment, True)
    fullattack = wrap(fullattack, ["user", "anything", "anything", optional("int"), optional("int"), optional("int")])

    def attackroll(self, irc, msg, args, user, charname, weapon, attackBonusAdjustment, ac, damageAdjustment):
        self.__doAttackRoll(irc, charname, weapon, attackBonusAdjustment, ac, damageAdjustment, False)
    attackroll = wrap(attackroll, ["user", "anything", "anything", optional("int"), optional("int"), optional("int")])

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

    def dailyuses(self, irc, msg, args, user, charname):
        """ List abilities with a daily use limit on the given character """
        chars = self.gameState.getChars(charname)
        if chars == []:
            irc.reply("Unknown character.")
            return

        s = ""
        for c in chars:
            if c.dailyUse:
                s += c.name + ":"
                for du in c.dailyUse:
                    s += " %s %d/%d" % (du["name"], du["used"], du["max"])
                s += " "

        irc.reply(s)
    dailyuses = wrap(dailyuses, ["user", "somethingWithoutSpaces"])

    def dailyuse(self, irc, msg, args, user, charname, uses, ability):
        """ <char> <uses> <ability> - change the uses of limited per day use ability by <uses>"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return
        
        du = c.useDailyAbility(ability, uses)
        if du:
            irc.reply("%s %d/%d" % (du["name"], du["used"], du["max"]))
        else:
            irc.reply("Unknown ability.")
    dailyuse = wrap(dailyuse, ["user", "somethingWithoutSpaces", "int", "text"])
    
    def cast(self, irc, msg, args, user, charname, spellname):
        # FIXME: add optional level adjustment for metamagic casting.
        """ <character> <spellname>"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return
        
        s = c.getSpell(spellname)
        if s is None:
            irc.reply("Unknown character.")

        r = "%s casts a %s spell, save is %s" % (c.name, s["name"], s.get("save"))
        irc.reply(r)            

        uses = c.cast(s, 0)
        if uses:
            irc.reply("%s %d/%d" % (uses["name"], uses["used"], uses["max"]))

    cast = wrap(cast, ["user", "somethingWithoutSpaces", "text"])

    def inventory(self, irc, msg, args, user, charname):
        """<charname> - lists inventory of given char"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        irc.reply(c.inventory.toString())
    inventory = wrap(inventory, ["user", "somethingWithoutSpaces"])

    def removeitem(self, irc, msg, args, user, charname, quantity, itemname):
        """<charname> <quantity> <itemname>"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        item = c.inventory.search(itemname)
        if item is None:
            irc.reply("%s doesn't seem to have any %s." % (c.name, itemname))

        c.inventory.quantityAdjustItem(item, -quantity)
        irc.reply("%d %s removed from inventory." % (quantity, item.name))

    removeitem = wrap(removeitem, ["user", "somethingWithoutSpaces", "positiveInt", "text"])

    # additem: charname intAmount namewithspaces (floatWeight)
    #addItemExp = re.compile("^(\w+)\s+([0-9]+)\s+([\w ]+)(?:\s+([0-9\.]+)$)?}")

    def additem(self, irc, msg, args, user, charname, quantity, itemname):
        """<charname> <amount> <item name>"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        i = item.Item(itemname, quantity)#, 0 if weight is None else weight)
        c.inventory.add(i)

        irc.reply("%d %s added to inventory." % (quantity, i.name))
    additem = wrap(additem, ["user", "somethingWithoutSpaces", "positiveInt", "text"])



Class = Pathfinder


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
