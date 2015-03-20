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
import jsonpickle
import random
import re

from operator import itemgetter
from .util import *
from . import item
from . import gamestate
from . import rollSemantics
from . import db
from . import spell

MaximumHeroLabXMLSize = 16777216

class Pathfinder(callbacks.Plugin):
    """Add the help for "@plugin help Pathfinder" here
    This should describe *how* to use this plugin."""

    def __init__(self, irc):
        self.__parent = super(Pathfinder, self)
        self.__parent.__init__(irc)
        self.rng = random.Random()   # create our rng
        self.rng.seed()   # automatically seeds with current time

        self.dataFile = conf.supybot.directories.data.dirize("PathFinderState.json")
        databasePath = conf.supybot.directories.data.dirize("pathfinder.sqlite")

        self.gameState = self.resumeState(self.dataFile)
        self.database = db.Database(databasePath)

        self.roller = rollSemantics.Roller(self.gameState, self.rng)
        self.partyRegExp = re.compile("^party ")
        
    def die(self):
        print("Pathfinder dying")
        self.saveState(self.dataFile)
        self.database.close()

    def flush(self):
        print("Pathfinder flushing.")
        self.saveState(self.dataFile)

    def resumeState(self, filename):
        gameState = gamestate.GameState()
        try:
            f = open(filename, "r")
            data = f.readline()
            f.close()
            gameState = jsonpickle.decode(data)
        except Exception as e:
            self.log.warning('Couldn\'t load gamestate: %s', str(e))

        return gameState

    def saveState(self, filename):
        try:
            f = utils.file.AtomicFile(filename)
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
        """saves the state of the current game"""
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
            s += " = %s" % result

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
            irc.reply("Error: " + str(e))

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
            hlXml = utils.web.getUrl(url, MaximumHeroLabXMLSize)
            count = self.gameState.hlImport(hlXml, partyMembers == True)
            irc.reply("%d characters imported" % count)
        except Exception as e:
            irc.reply("Import failed: %s" % str(e))

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

    def removecharacter(self, irc, msg, args, charName, user):
        """Remove character with given name"""
        c = self.gameState.getChar(charName)
        if c is not None and self.gameState.removeCharacter(c):
            irc.reply("{} removed".format(c.name))
        else:
            irc.reply("Unknown character")

    removecharacter = wrap(removecharacter, ["anything", "user"])

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
            adjustment, trace = self.roller.doRoll(text)
        except Exception as e:
            self.log.warning(str(e))
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

        damagedOrHealed = "damaged" if isDamage else "healed"
        if trace == str(adjustment):
            s += " is %s for %d hp" % (damagedOrHealed, adjustment)
        else:
            s += " is %s for %d hp (%s)" % (damagedOrHealed, adjustment, trace)

        c.set("hp", hp)

        if totalhp is None:
            irc.reply("%s, now has %d hp." % (s, hp))
        else:
            irc.reply("%s, now has %d/%d hp." % (s, hp, totalhp))


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
        c = self.gameState.getChar(charname)
        if c is not None and self.gameState.initOrderRemove(c):
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
            roll = random.randint(1, 20)

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

    def spells(self, irc, msg, args, user, charname, level):
        """list known spells on given character"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character")
            return

        if len(c.spellCaster) == 0:
            irc.reply("{} is not a spellcaster.".format(c.name))

        for caster in c.spellCaster.values():
            if level is None or level <= caster.highestSpellLevel():
                irc.reply('{}: {}'.format(caster.casterClass, caster.getSpellListString(level)))
            else:
                irc.reply("Invalid spelllevel")

    spells = wrap(spells, ["user", "anything", optional("nonNegativeInt")])

    def __getSpell(self, spellname):
        candidates = spell.Spell.searchByName(self.database, spellname)

        return min(candidates, key=lambda s: len(s.name)) if candidates != [] else None

    def spell(self, irc, msg, args, user, spellname):
        """ give details on a spell """
        s = self.__getSpell(spellname)
        if s is None:
            irc.reply("Unknown spell")
        else:
            irc.reply(s.shortString())

    spell = wrap(spell, ["user", "text"])

    def __replyWithSpellUse(self, c, irc, level):
        for caster in c.spellCaster.values():
            if level is None or level <= caster.highestSpellLevel():
                irc.reply('{}: {}'.format(caster.casterClass, caster.getSpellUsage(level)))
            else:
                irc.reply("Invalid spelllevel")

    def spelluse(self, irc, msg, args, user, charname, level):
        """ get used spells"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        if len(c.spellCaster) == 0:
            irc.reply("{} is not a spellcaster.".format(c.name))

        self.__replyWithSpellUse(c, irc, level)

    spelluse = wrap(spelluse, ["user", "anything", optional("nonNegativeInt")])

    def __getPrefixedNumber(self, s):
        l = s.split(' ')
        if len(l) <= 1:
            return None, s
        elif l[0].isdigit():
            return int(l[0]), ' '.join(l[1:])
        else:
            return None, s

    def __getPostFixedSpellLevel(self, s):
        m = re.match('([\w ]+)@(\d)', s)
        if m is None:
            return s, None
        else:
            return m.group(1).strip(), int(m.group(2))

    def __getSpellName(self, s):
        count, spell = self.__getPrefixedNumber(s)
        spell, spellLevel = self.__getPostFixedSpellLevel(spell)
        return count if count else 1, spell, spellLevel

    def __getSpellList(self, spells):
        if spells is None or spells.strip() == '':
            raise RuntimeError("Empty spell list.")

        list = []
        for s in map(lambda s: s.strip(), spells.split(',')):
            list.append(self.__getSpellName(s))

        return list

    def __convertToCastableSpells(self, casts, spellname, spellLevel, caster):
        s = self.__getSpell(spellname)
        if s is None:
            raise RuntimeError("Unknown spell '{}'.".format(spellname))

        # If no spellLevel override is supplied, look it up
        if spellLevel is None:
            spellLevel = s.getSpellLevel(caster.casterClass)
        if spellLevel is None:
            raise RuntimeError("You cannot cast {}".format(s.spell.name))
        elif spellLevel > caster.highestSpellLevel():
            raise RuntimeError("Spelllevel of {} is higher than you can cast".format(s.spell.name))

        return spell.CastableSpell(s, casts, casts, caster.casterClass, spellLevel)

    def preparespells(self, irc, msg, args, user, charname, classname, spellList):
        """ preparespells <charname> (class name) (comma seperated list of spells) """
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        if classname is None or classname == "":
            self.__replyWithSpellUse(c, irc, None)
            return

        caster = subStringMatchDictKey(c.spellCaster, classname)
        if caster is None:
            irc.reply("{} isn't a spellcasting class on {}".format(classname, c.name))
            return
        else:
            caster = caster[1]

        if not isinstance(caster, spell.PreparedCaster):
            irc.reply("{}'s {} class doesn't need to prepare spells.".format(c.name, caster.casterClass))
            return

        try:
            spellList = self.__getSpellList(spellList)
            spellList = map(lambda s: self.__convertToCastableSpells(s[0], s[1], s[2], caster), spellList)
            for s in spellList:
                if not caster.prepareSpell(s):
                    raise RuntimeError("Not enough spells slots for {} {} spell.".format(s.castsLeft, s.spell.name))

            self.__replyWithSpellUse(c, irc, None)
        except RuntimeError as e:
            irc.reply(str(e))

    preparespells = wrap(preparespells, ["user", "anything", optional("anything"), optional("text")])

    def clearspells(self, irc, msg, args, user, charname):
        """ <charname> (classname)"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        preparedClasses = list(filter(lambda sc: isinstance(sc, spell.PreparedCaster), c.spellCaster.values()))
        for pc in preparedClasses:
            pc.resetSpellList()

        if len(preparedClasses) > 0:
            irc.reply("Spelllist{} cleared.".format('s' if len(preparedClasses) > 1 else ''))
        else:
            irc.reply("Not a prepared spell caster.")

    clearspells = wrap(clearspells, ["user", "anything"])

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

    def attackdetails(self, irc, msg, args, user, charname, attackName):
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
    
    attackdetails = wrap(attackdetails, ["user", "anything", "anything"])

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

    attackExp = re.compile('(\w+) (?:"([^"]*)"|(\w+)) ?(?:ac[ ]?(\d+))? ?([+\-]?\d+)? ?([+\-]?\d+)?')

    def parseAttackRollArgs(self, args):
        m = Pathfinder.attackExp.match(args)

        if m is not None:
            charName = m.group(1)
            attack = m.group(2) if m.group(2) else m.group(3)

            ac = tryToConvertValue(m.group(4))
            attackMod = int(m.group(5)) if m.group(5) is not None else 0
            damageMod = int(m.group(6)) if m.group(6) is not None else 0

            return (charName, attack, attackMod, damageMod, ac)
        else:
            raise RuntimeError("Invalid arguments")

    def fullattackroll(self, irc, msg, args):
        """ <char> <weapon> [attack bonus adjustment] [target ac] [bonus damage] """
        try:
            charname, weapon, attackBonusAdjustment, damageAdjustment, ac = self.parseAttackRollArgs(args)
            self.__doAttackRoll(irc, charname, weapon, attackBonusAdjustment, ac, damageAdjustment, True)
        except RuntimeError:
            irc.reply("Invalid arguments")
    fullattackroll = wrap(fullattackroll, ["user", "text"])

    def attackroll(self, irc, msg, args, user, charname, weapon, attackBonusAdjustment, ac, damageAdjustment):
        """ <char> <weapon> [attack bonus adjustment] [target ac] [bonus damage] """
        try:
            charname, weapon, attackBonusAdjustment, damageAdjustment, ac = self.parseAttackRollArgs(args)
            self.__doAttackRoll(irc, charname, weapon, attackBonusAdjustment, ac, damageAdjustment, False)
        except RuntimeError:
            irc.reply("Invalid arguments")
    attackroll = wrap(attackroll, ["user", "text"])


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
            
    swap = wrap(swap, ["user", "anything", "anything"])

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
                for name, du in c.dailyUse.items():
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

    def __castSpell(self, irc, charname, spellname, cast):
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        count, spellname, spellLevel = self.__getSpellName(spellname)
        caster, s = c.getSpell(spellname, spellLevel)
        if s is None:
            irc.reply("You don't know {}.".format(spellname))
            return

        try:
            if cast:
                caster.cast(s, spellLevel)
            else:
                caster.uncast(s, spellLevel)

            irc.reply("{} {} a {}{} spell.".format(c.name, "casts" if cast else "uncasts", s.spell.name, "" if spellLevel is None else " @{}".format(spellLevel)))
            if isinstance(caster, spell.SpontaneousCaster):
                self.__replyWithSpellUse(c, irc, None)
            else:
                irc.reply(str(s))
        except RuntimeError as e:
            irc.reply(str(e))

    def cast(self, irc, msg, args, user, charname, spellname):
        """ <character> <spellname>"""
        self.__castSpell(irc, charname, spellname, True)
    cast = wrap(cast, ["user", "somethingWithoutSpaces", "text"])

    def uncast(self, irc, msg, args, user, charname, spellname):
        """ <character> <spellname>"""
        self.__castSpell(irc, charname, spellname, False)
    uncast = wrap(uncast, ["user", "somethingWithoutSpaces", "text"])

    def inventory(self, irc, msg, args, user, charname):
        """<charname> - lists inventory of given char"""
        c = self.gameState.getChar(charname)
        if c is None:
            irc.reply("Unknown character.")
            return

        irc.reply(c.inventory.__str__())
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
