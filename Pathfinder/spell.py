if __package__ != '':
    from .util import *
else:
    from util import *

import operator


class Spell(DictEncapsulator):
    def __init__(self, dict = {}):
        self.__initFields(dbColumns)
        super(Spell, self).__init__(dict)

    def schoolString(self):
        if self.subschool is None or self.subschool == "":
            return self.school
        else:
            return '{} ({})'.format(self.school, self.subschool)

    def shortString(self):
        s = "{}: {} {}. Casting Time: {}. Components: {}.".format(self.name, self.schoolString(), self.spellLevel, self.castingTime, self.components)

        if self.domain:
            s += " Domains: {}.".format(self.domain)
        if self.range:
            s += " Range: {}.".format(self.range)
        if self.target:
            s += " Target: {}.".format(self.target)
        if self.duration:
            s += " Duration: {}.".format(self.duration)
        if self.savingThrow:
            s += " Saving Throw: {}.".format(self.savingThrow)
        if self.spellResistance:
            s += " Spell Resistance: {}.".format(self.spellResistance)
        if self.area:
            s += " Area: {}.".format(self.area)
        if self.effect:
            s += " Effect: {}.".format(self.effect)
        if self.link:
            s += " {}".format(self.link)

        return s

    def __getSpellLevel(self, spellList):
        index = self.spellLevel.find(spellList)
        if index == -1:
            return None
        else:
            return int(self.spellLevel[index + len(spellList) + 1])

    def __getHunterSpellLevel(self):
        druid = self.getSpellLevel("druid")
        ranger = self.getSpellLevel("ranger")

        if druid is not None and ranger is not None:
            return min(druid, ranger)
        else:
            if druid is not None and druid <= 6:
                return druid
            if ranger is not None:
                return ranger

        return None

    def getSpellLevel(self, className):
        className = className.lower()

        if className not in spellLists:
            return None

        if className != "hunter":
            return self.__getSpellLevel(spellLists[className])
        else:
            return self.__getHunterSpellLevel()

    def __initFields(self, columns):
        for c in dbColumns:
            self.__setattr__(c[1], None)

    @staticmethod
    def initFromDB(db, id):
        select = db.prepareSelectColumns("spells", dbColumns)
        select += ' where "id" = ?'

        return Spell(db.selectOne(select, (id,)))

    @staticmethod
    def searchByName(db, name):
        select = db.prepareSelectColumns("spells", dbColumns)
        select += ' where "name" like ?'

        name = "%{}%".format(name)

        return list(map(lambda d: Spell(d), db.selectMany(select, (name,))))

class CastableSpell(object):
    def __init__(self, spell, castsPrepared, castsLeft, casterClass, level):
        self.spell = spell
        self.castsPrepared = castsPrepared
        self.castsLeft = castsLeft
        self.casterClass = casterClass
        self.level = level

    def __str__(self):
        return "{} {}/{}".format(self.spell.name, self.castsLeft, self.castsPrepared)


class Spellcaster(object):
    def __init__(self, casterClass, casterLevel, usedSlots, maxSlots, baseSpellDC = 10, concentrationCheck = 10, overcomeSR = 0, source = ""):
        self.casterClass = casterClass.lower()
        self.casterLevel = casterLevel
        self.baseSpellDC = baseSpellDC
        self.concentrationCheck = concentrationCheck
        self.overcomeSR = overcomeSR
        self.source = source

        self.usedSpellSlots = usedSlots
        self.maxSpellSlots = maxSlots
        self.castableSpells = []  # List of CastableSpell

    def getSpells(self):
        return self.castableSpells

    def getSpellListString(self, level = None):
        spells = self.castableSpells if level is None else filter(lambda s: s.level == level, self.castableSpells)
        return ', '.join(map(str, spells))

    def cast(self, castableSpell, level):
        pass

    def uncast(self, castableSpell, level):
        pass

    def resetSpellUsage(self):
        pass

    def assignSpells(self, spellList):
        self.castableSpells.sort(key = operator.attrgetter('level', 'spell.name'))

    def highestSpellLevel(self):
        return len(self.maxSpellSlots) - 1

    def isLegalSpell(self, castableSpell):
        return castableSpell.level <= self.highestSpellLevel()

    def consumeSpellSlot(self, spellLevel, slots = 1):
        self.usedSpellSlots[spellLevel] += slots

    def remainingSpellSlots(self, spellLevel):
        return self.maxSpellSlots[spellLevel] - self.usedSpellSlots[spellLevel]

    def getSpellSlots(self, level):
        return self.maxSpellSlots[level]


    def getSpellsAtLevelCount(self, level, list):
        sum = 0
        for s in list:
            sum += s.castsPrepared
        return sum

    def prepareSpell(self, castableSpell):
        pass

    def getSpellUsage(self, level = None):
        usage = lambda l: 'L{} {}/{}'.format(l, self.usedSpellSlots[l], self.maxSpellSlots[l])

        if level is None:
            return ' '.join(map(usage, range(0, self.highestSpellLevel() + 1)))
        else:
            return usage(level)

    def getSpell(self, name, level):
        pass

class SpontaneousCaster(Spellcaster):
    def __init__(self, casterClass, casterLevel, usedSlots, maxSlots, baseSpellDC = 10, concentrationCheck = 10, overcomeSR = 0, source = ""):
        super().__init__(casterClass, casterLevel, usedSlots, maxSlots, baseSpellDC, concentrationCheck, overcomeSR, source)

    def assignSpells(self, spellList):
        for s in spellList:
            if self.isLegalSpell(s):
                self.castableSpells.append(s)

        super().assignSpells(spellList)

    def resetSpellUsage(self):
        self.usedSpellSlots = [0] * len(self.maxSpellSlots)
        for s in self.castableSpells:
            s.castsLeft = s.castsPrepared

    def cast(self, castableSpell, levelOverride):
        spellLevel = levelOverride if levelOverride is not None else castableSpell.level

        # Cantrips and Orisons aren't consumed
        if spellLevel == 0:
            return

        if spellLevel > self.highestSpellLevel() or self.remainingSpellSlots(spellLevel) <= 0:
            raise RuntimeError("You can't cast any more level {} spells".format(spellLevel))

        for s in self.castableSpells:
            if s.level == spellLevel:
                s.castsLeft -= 1

        self.consumeSpellSlot(spellLevel, 1)


    def uncast(self, castableSpell, levelOverride):
        if castableSpell.castsLeft == castableSpell.castsPrepared:
            raise RuntimeError("No more {} casts to undo".format(castableSpell.spell.name))

        spellLevel = levelOverride if levelOverride is not None else castableSpell.level

        # Cantrips and Orisons aren't consumed
        if spellLevel == 0:
            return

        for s in self.castableSpells:
            if s.level == spellLevel:
                s.castsLeft += 1

        self.consumeSpellSlot(spellLevel, -1)

    # A spontaneous caster will only have the spell appear once in castableSpells, so ignore the level argument.
    def getSpell(self, name, level):
        name = name.lower()
        matchSpellName = lambda s: s.spell.name.lower().find(name) > -1
        compareMatchLength = lambda a, b: len(a.spell.name) > len(b.spell.name)

        return findBest(matchSpellName, compareMatchLength, self.castableSpells)

class PreparedCaster(Spellcaster):
    def __init__(self, casterClass, casterLevel, maxSlots, baseSpellDC = 10, concentrationCheck = 10, overcomeSR = 0, source = ""):
        super().__init__(casterClass, casterLevel, [0] * len(maxSlots), maxSlots, baseSpellDC, concentrationCheck, overcomeSR, source)

    def assignSpells(self, spellList):
        for s in spellList:
            if self.isLegalSpell(s):
                self.castableSpells.append(s)

                self.consumeSpellSlot(s.level, s.castsLeft)

        super().assignSpells(spellList)

    def cast(self, castableSpell, levelOverride):
        # No level override, spellevel is set when is spell is prepared, so ignore parameter
        if castableSpell.castsLeft <= 0:
            raise RuntimeError("No more {} casts available".format(castableSpell.spell.name))

        # Cantrips and Orisons aren't consumed
        if castableSpell.level == 0:
            return

        castableSpell.castsLeft -= 1

        return

    def uncast(self, castableSpell, levelOverride):
        # No level override, spellevel is set when is spell is preparedm so ignore parameter
        if castableSpell.castsLeft == castableSpell.castsPrepared:
            raise RuntimeError("No more {} casts to undo".format(castableSpell.spell.name))

        # Cantrips and Orisons aren't consumed
        if castableSpell.level == 0:
            return True

        castableSpell.castsLeft += 1

        return True

    def resetSpellUsage(self):
        for s in self.castableSpells:
            s.castsLeft = s.castsPrepared

    def resetSpellList(self):
        self.castableSpells = []
        self.usedSpellSlots = [0] * len(self.maxSpellSlots)

    def prepareSpell(self, castableSpell):
        alreadyPrepared = list(filter(lambda s: s.spell.name == castableSpell.spell.name and s.level == castableSpell.level, self.castableSpells))
        if alreadyPrepared != []:
            alreadyPrepared[0].castsLeft += castableSpell.castsLeft
            alreadyPrepared[0].castsPrepared += castableSpell.castsPrepared
            return True

        if self.usedSpellSlots[castableSpell.level] + castableSpell.castsPrepared <= self.maxSpellSlots[castableSpell.level]:
            self.castableSpells.append(castableSpell)
            self.usedSpellSlots[castableSpell.level] += castableSpell.castsPrepared
            return True

        return False

    # Prepared casters prepare a spell at a certain level, so a level 3 and maximised level 6 fireball both get stored
    # in castableSpells, so we need to differentiate on level as well if it's supplied
    def getSpell(self, name, level):
        name = name.lower()
        if level is None:
            matchSpell = lambda s: s.spell.name.lower().find(name) > -1
        else:
            matchSpell = lambda s: s.spell.name.lower().find(name) > -1 and s.level == level

        compareMatchLength = lambda a, b: len(a.spell.name) > len(b.spell.name)

        return findBest(matchSpell, compareMatchLength, self.castableSpells)

spellLists = {
    "bard": "bard",
    "cleric": "cleric/oracle",
    "druid": "druid",
    "paladin": "paladin",
    "ranger": "ranger",
    "sorcerer": "sorcerer/wizard",
    "wizard": "sorcerer/wizard",
    "alchemist": "alchemist",
    "inquisitor": "inquisitor",
    "magus": "magus",
    "oracle": "cleric/oracle",
    "summoner": "summoner",
    "witch": "witch",
    "arcanist": "sorcerer/wizard",
    "bloodrager": "bloodrager",
    "hunter": ["druid", "ranger"],  # only to level 6 druid spells
    "investigator": "alchemist",
    "shaman": "shaman",
    "skald": "bard",
    "warpriest": "cleric/oracle"
}

dbColumns = [
    ('name', 'name'),
    ('school', 'school'),
    ('subschool', 'subschool'),
    ('descriptor', 'descriptor'),
    ('spell_level', 'spellLevel'),
    ('casting_time', 'castingTime'),
    ('components', 'components'),
    ('costly_components', 'costlyComponents'),
    ('range', 'range'),
    ('area', 'area'),
    ('effect', 'effect'),
    ('targets', 'target'),
    ('duration', 'duration'),
    ('dismissible', 'dismissible'),
    ('shapeable', 'shapeable'),
    ('saving_throw', 'savingThrow'),
    ('spell_resistence', 'spellResistance'),
    ('description', 'description'),
    #('description_formated', 'description_formated'),
    ('source', 'source'),
    #('full_text', 'fullText'),
    ('verbal', 'verbal'),
    ('somatic', 'somatic'),
    ('material', 'material'),
    ('focus', 'focus'),
    ('divine_focus', 'divineFocus'),
    ('deity', 'deity'),
    ('SLA_Level', 'spellLikeAbilityLevel'),
    ('domain', 'domain'),
    ('short_description', 'shortDescription'),
    ('acid', 'acid'),
    ('air', 'air'),
    ('chaotic', 'chaotic'),
    ('cold', 'cold'),
    ('curse', 'curse'),
    ('darkness', 'darkness'),
    ('death', 'death'),
    ('disease', 'disease'),
    ('earth', 'earth'),
    ('electricity', 'electricity'),
    ('emotion', 'emotion'),
    ('evil', 'evil'),
    ('fear', 'fear'),
    ('fire', 'fire'),
    ('force', 'force'),
    ('good', 'good'),
    ('language_dependent', 'languageDependent'),
    ('lawful', 'lawful'),
    ('light', 'light'),
    ('mind_affecting', 'mindAffecting'),
    ('pain', 'pain'),
    ('poison', 'poison'),
    ('shadow', 'shadow'),
    ('sonic', 'sonic'),
    ('water', 'water'),
    ('linktext', 'link'),
    ('id', 'id'),
    ('material_costs', 'materialCosts'),
    ('bloodline', 'bloodline'),
    ('patron', 'patron'),
    ('mythic_text', 'mythicText'),
    ('augmented', 'augmented'),
    ('mythic', 'mythic'),
    ('sor', 'sorcerer'),
    ('wiz', 'wizard'),
    ('cleric', 'cleric'),
    ('druid', 'druid'),
    ('ranger', 'ranger'),
    ('bard', 'bard'),
    ('paladin', 'paladin'),
    ('alchemist', 'alchemist'),
    ('summoner', 'summoner'),
    ('witch', 'witch'),
    ('inquisitor', 'inquisitor'),
    ('oracle', 'oracle'),
    ('antipaladin', 'antipaladin'),
    ('magus', 'magus'),
    ('adept', 'adapt'),
    ('bloodrager', 'bloodrager'),
    ('shaman', 'shaman')
]
