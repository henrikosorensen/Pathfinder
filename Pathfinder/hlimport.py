if __package__ != '':
    from . import character
    from . import item
    from . import attack
    from . import spell
    from .util import *
    from .abbreviations import abbreviations
else:
    import character
    import item
    import attack
    import spell
    from util import *
    from abbreviations import abbreviations


import xml.etree.ElementTree as ET

coinValues = {
    "pp": 10,
    "gp": 1,
    "ep": 0.5,
    "sp": 0.1,
    "cp": 0.01
}

def getGoldValue(pp, gp, sp, cp, ep = 0):
    return pp * 10 + gp + sp / 10.0 + cp / 100.0 + ep / 2

def cloneAttributes(e):
    d = {}
    for key, value in e.items():
        value = tryToConvertValue(value)
        d[key] = value

    return d

class ParsingException(Exception):
    pass

class HeroLabPfImporter(object):
    #def __init__(self, db):
    #    self.database = db

    def getClass(self, classET, charET):
        name = classET.get("name")
        level = classET.get("level")

        # Not a spell casting class
        if classET.get("spells", "") == "":
            return character.Class.initFromHl(name, level), []
        else:
            # Find <spellclass> tag for this class.
            sc = find(lambda c: c.get("name") == name, charET.find("spellclasses"))
            if sc is not None:
                spellCasters = []
                charClass = character.Class.initFromHl(name, level)
                sc = self.spellclass(sc)

                baseSpellDC = int(classET.get("basespelldc", 10))
                casterLevel = int(classET.get("casterlevel", 0))
                concentrationCheck = int(classET.get("concentrationcheck", 0))
                overcomeSR = int(classET.get("overcomespellresistance"))
                source = classET.get("castersource")

                spontaneous = sc["spontaneous"]
                max = sc["max"]
                used = sc["used"]

                def toCastableSpell(tuple):
                    className, castsLeft, s, spellLevel = tuple

                    # spells in <spellsknown> tag doesn't contain a castsleft value, insert it manually.
                    if castsLeft is None:
                        castsLeft = max[spellLevel] - used[spellLevel]

                    if spontaneous:
                        castsPrepared = max[spellLevel]
                    else:
                        if spellLevel == 0:
                            castsLeft = 1

                        castsPrepared = castsLeft

                    return spell.CastableSpell(s, castsPrepared, castsLeft, className, spellLevel)

                if spontaneous:
                    spellCaster = spell.SpontaneousCaster(charClass.name, casterLevel, used, max, baseSpellDC, concentrationCheck, overcomeSR, source)
                    spellCasters.append(spellCaster)
                else:
                    spellCaster = spell.PreparedCaster(charClass.name, casterLevel, max, baseSpellDC, concentrationCheck, overcomeSR, source)
                    spellCasters.append(spellCaster)

                    domains = self.getDomains(name, charET)
                    if len(domains) > 0:
                        domainSlots = [0] + [1] * (len(max) - 1)
                        domainCaster = spell.PreparedCaster("domain", casterLevel, domainSlots, baseSpellDC, concentrationCheck, overcomeSR, source)
                        spellCasters.append(domainCaster)

                for each in spellCasters:
                    # filter out spells not from this class.
                    spellList = self.getSpells(spontaneous, charET)

                    spellList = filter(lambda sp: sp[0].lower() == each.casterClass.lower(), spellList)
                    spellList = filter(lambda sp: sp[2].spellLevel <= each.highestSpellLevel(), spellList)
                    spellList = list(map(toCastableSpell, spellList))

                    each.assignSpells(spellList)

                return charClass, spellCasters
            else:
                raise RuntimeError("Cannot find spellclass tag for class {}".format())


    def getDomains(self, fullClassName, charET):
        domains = []
        otherSpecialsET = charET.find("otherspecials")

        for specialET in otherSpecialsET:
            exp = "{} Domain".format(fullClassName)
            if specialET.get("name").startswith(exp):
                domains.append(specialET.get("shortname"))

        return domains

    def classes(self, c, charET):
        classesET = charET.find("classes")
        c.set("level", classesET.get("level"))
        c.set("class", classesET.get("summary"))

        c.classes = {}
        for classET in classesET:
            cl, caster = self.getClass(classET, charET)
            c.classes[cl.name] = cl

            for each in caster:
                c.spellCaster[each.casterClass] = each

    def getSpells(self, spontaneous, charET):
        spells = []
        for s in charET.find("spellsknown" if spontaneous else "spellsmemorized"):
            spells.append(self.getSpell(s))

        return spells

    def gold(self, charET):
        money = charET.find("money")
        gp = getGoldValue(int(money.get("pp")), int(money.get("gp")), int(money.get("sp")), int(money.get("cp")))
        return gp


    def languages(self, charET):
        languages = []
        for l in charET.find("languages"):
            languages.append(l.get("name"))
        return ', '.join(languages)


    def abilityScores(self, charET):
        abilities = {}
        for a in charET.find("attributes"):
            stat = a.get("name").lower()
            value = int(a.find("attrvalue").get("modified"))
            baseValue = int(a.find("attrvalue").get("base"))

            abilities[stat] = value
            abilities[stat + " bonus"] = int(a.find("attrbonus").get("modified"))
            abilities["base " + stat] = baseValue
            abilities["base " + stat + " bonus"] =  int(a.find("attrbonus").get("base"))

        return abilities

    def saves(self, charET):
        saves = {}
        for s in charET.find("saves"):
            if s.tag == "save":
                name = s.get("name").lower()
                value = int(s.get("save"))
                saves[name] = value
        return saves

    def armourClass(self, charET):
        armour = {}

        ac = charET.find("armorclass")

        armour["ac"] = tryToConvertValue(ac.get("ac"))
        armour["touch ac"] = tryToConvertValue(ac.get("touch"))
        armour["flatfooted AC"] = tryToConvertValue(ac.get("flatfooted"))

        penalties = charET.find("penalties")

        for p in penalties:
            if p.get("name") == "Armor Check Penalty":
                armour["acp"] = int(p.get("value"))
            if p.get("name") == "Max Dex Bonus":
                armour["max dexterity bonus"] = tryToConvertValue(p.get("value"))

        return armour

    def initiative(self, c, charET):
        init = charET.find("initiative")
        return int(init.get("total"))


    def movementSpeed(self, charET):
        movement = charET.find("movement").find("speed")
        return int(movement.get("value"))

    def skill(self, s):
        skill = {
            "name": s.get("name"),
            "value:": int(s.get("value")),
            "ability": abbreviations[s.get("attrname").lower().capitalize()],
            "ability bonus": int(s.get("attrbonus")),
            "class skill": isStrBoolTrue(s.get("classskill", "no")),
            "ranks": int(s.get("ranks")),
            "armor check penalty": isStrBoolTrue(s.get("armorcheck", "no"))
        }
        return skill

    def skills(self, c, charET):
        skills = {}
        for s in charET.find("skills"):
            if s.tag == "skill":
                skill = self.skill(s)
                c.skills[skill["name"]] = skill
                skills[s.get("name").lower()] = int(s.get("value"))

        return skills

    def feats(self, charET):
        feats = []
        for f in charET.find("feats"):
            if f.tag == "feat":
                feats.append(f.get("name"))
        return ', '.join(feats)


    def getSpell(self, s):
        castsLeft = tryToConvertValue(s.get("castsleft"))
        casterClass = s.get("class").lower()
        spellName = s.get("name")
        spellLevel = int(s.get("level"))

        # Annoyingly Domain spells seem to get the class="" attribute
        if casterClass == "":
            casterClass = "domain"

        spellData = spell.Spell(self.spellDict(s))

        #dbSpell = spell.Spell.searchByName(self.database, spellName)

        #if len(dbSpell) < 1:
        #    raise RuntimeError("Spell {0} not found".format(spellName))
        #else:
        #    dbSpell = dbSpell[0]

        return casterClass, castsLeft, spellData, spellLevel

    def spellDict(self, s):
        spell = {}
        spell["name"] = s.get("name")
        spell["spellLevel"] = int(s.get("level"))
        spell["class"] = s.get("class").lower()
        spell["school"] = s.get("schooltext")
        spell["subschool"] =  s.get("subschooltext")
        spell["castingTime"] = s.get("casttime")
        spell["components"] = s.get("componenttext")
        spell["range"] = s.get("range")
        spell["target"] = s.get("target")
        spell["duration"] = s.get("duration")
        spell["savingThrow"] = s.get("save")
        spell["spellResistance"] = s.get("resisttext")
        spell["area"] = s.get("area")
        spell["effect"] = s.get("effect")
        spell["link"] = ""

        # Annoyingly Domain spells seem to get the class="" attribute
        if spell["class"] == "":
            spell["class"] = "domain"

        return spell

    def items(self, c, charET):
        itemETs = charET.find("magicitems").findall("item")
        itemETs.extend(charET.find("gear").findall("item"))
        for i in itemETs:
            weight = i.find("weight")
            cost = i.find("cost")

            it = item.Item(i.get("name"),
                           int(i.get("quantity")),
                           float(weight.get("value")),
                           float(cost.get("value")))
            c.addToInventory(it)

    def createAttack(self, attackData):
        a = attack.Attack(attack["name"])
        a.bonus = attack.attackBonus(attackData["attack"])
        a.damageText = attackData["damage"]
        a.damageRoll = attack.getDamageRoll(attackData["damage"])
        a.quantity = attackData.get("quantity")

        critRange = attack.critical(attackData["crit"])
        a.criticalRange = critRange[0]
        a.criticalMultiplier = critRange[1]

        a.category = attackData.get("category")
        a.equipped = attackData.get("equipped")
        a.damageType = attackData.get("typetext")

        return a

    def attacks(self, c, charET):
        rangedAttacks = charET.find("ranged")
        for weapon in rangedAttacks:
            if weapon.tag == "weapon":
                a = cloneAttributes(weapon)
                a = self.createAttack(a)
                c.attacks[a.name] = a
        meleeAttacks = charET.find("melee")
        for weapon in meleeAttacks:
            if weapon.tag == "weapon":
                a = cloneAttributes(weapon)
                a = self.createAttack(a)
                c.attacks[a.name] = a

    def trackedResources(self, charET):
        trackedResources = charET.find("trackedresources")

        resources = {}
        for r in trackedResources:
            name = r.get("name")
            used = int(r.get("used"))
            max = int(r.get("max"))
            daily = r.get("name").find("/day") != -1

            resources[name] = character.TrackedResource(name, used, max, daily)

        return resources

    def spellclass(self, sc):
        spellLevels = sc.findall("spelllevel")
        spellClass = {
            "name": sc.get("name"),
            "spontaneous": sc.get("spells").lower() == "spontaneous",
            "memorised": sc.get("spells").lower() == "memorized",
            "levels": len(spellLevels) - 1,
            "max": [-1] * len(spellLevels),
            "used": [-1] * len(spellLevels)
        }

        for l in spellLevels:
            level = int(l.get("level"))
            max = int(l.get("maxcasts", 0))
            used = int(l.get("used"))

            spellClass["used"][level] = used
            spellClass["max"][level] = max

        return spellClass
    #
    # def spellclasses(c, charET):
    #     spellclasses = charET.find("spellclasses")
    #     for sc in spellclasses:
    #         if sc.get("spells").lower() == "spontaneous":
    #             for sl in sc:
    #                 if not sl.get("unlimited"):
    #                     spellLevel = {
    #                         "name": "Level %s %s spells" % (sl.get("level"), sc.get("name")),
    #                         "level": int(sl.get("level")),
    #                         "used": int(sl.get("used")),
    #                         "max": int(sl.get("maxcasts")),
    #                         "class": sc.get("name"),
    #                         "spontaneousSpellCasts": True
    #                     }
    #                     c.dailyUse[spellLevel["name"]] = spellLevel


    def health(self, charET):
        health = charET.find("health")
        return {
            "hp": int(health.get("currenthp")),
            "totalhp": int(health.get("hitpoints"))
        }


    def personal(self, charET):
        personalData = charET.find("personal")
        return {
            "gender": personalData.get("gender"),
            "age": tryToConvertValue(personalData.get("age")),
            "hair": personalData.get("hair"),
            "eyes": personalData.get("eyes"),
            "skin": personalData.get("skin"),
            "weight": tryToConvertValue(personalData.find("charweight").get("value")),
            "height": personalData.find("charheight").get("text")
        }



    def getListOfAttributes(self, attribute, tags):
        attributes = []

        for tag in tags:
            attributes.append(tag.get(attribute))

        return ', '.join(attributes)

    def resistance(self, charET):
        resistances = []

        resistanceET = charET.find(resistances)

        for r in resistanceET.findall("special"):
            resistances.append(r.get("shortname"))

    def maneuvers(self, charET):
        maneuversET = charET.find("maneuvers")

        combatManeuvers = {
            "cmd": tryToConvertValue(maneuversET.get("cmd")),
            "cmb": tryToConvertValue(maneuversET.get("cmb")),
            "flatfooted cmd": tryToConvertValue(maneuversET.get("cmd"))
        }
        maneuvers = []
        for m in maneuversET.findall("maneuvertype"):
            name = m.get("name").lower()
            combatManeuvers["%s cmb" % name] = tryToConvertValue(m.get("cmb"))
            combatManeuvers["%s cmd" % name] = tryToConvertValue(m.get("cmd"))
            combatManeuvers["%s bonus" % name] = tryToConvertValue(m.get("bonus"))
            maneuvers.append(name)

        combatManeuvers["maneuvers"] = ', '.join(maneuvers)

        return combatManeuvers

    def encumbrance(self, charET):
        encumberET = charET.find("encumbrance")
        return {
            "encumbrance" : tryToConvertValue(encumberET.get("carried")),
            "light encumbrance": tryToConvertValue(encumberET.get("light")),
            "medium encumbrance": tryToConvertValue(encumberET.get("medium")),
            "heavy encumbrance": tryToConvertValue(encumberET.get("heavy"))
        }

    def importCharacter(self, charET):
        #charET = charTrees.pop()

        c = character.Character(charET.get("name"))
        #characters.append(c)

        #minions = charET.find("minions").findall("character")
        #charTrees.extend(minions)

        c.set("name", c.name)
        c.set("race", charET.find("race").get("name"))
        c.set("size", charET.find("size").get("name"))
        c.set("alignment", charET.find("alignment").get("name"))
        c.set("deity", charET.find("deity").get("name"))
        c.set("xp", charET.find("xp").get("total"))
        c.set("size", charET.find("size").get("name"))
        c.set("cr", tryToConvertValue(charET.find("challengerating").get("value")))
        c.set("base attack bonus", tryToConvertValue(charET.find("attack").get("baseattack")))

        c.stats.update(self.personal(charET))
        c.set("resistance", self.getListOfAttributes("shortname", charET.find("resistances").findall("special")))
        c.set("dr", self.getListOfAttributes("shortname", charET.find("damagereduction").findall("special")))
        c.set("immunity", self.getListOfAttributes("shortname", charET.find("immunities").findall("special")))
        c.stats.update(self.maneuvers(charET))
        c.stats.update(self.encumbrance(charET))

        c.stats.update(self.health(charET))
        self.classes(c, charET)
        c.set("gold", self.gold(charET))
        c.set("languages", self.languages(charET))
        c.stats.update(self.abilityScores(charET))
        c.stats.update(self.saves(charET))
        c.stats.update(self.armourClass(charET))
        c.set("initiative", self.initiative(c, charET))
        c.set("speed", self.movementSpeed(charET))
        c.stats.update(self.skills(c, charET))
        c.set("feats", self.feats(charET))
        self.items(c, charET)
        self.attacks(c, charET)
        c.trackedResources = self.trackedResources(charET)

        bab = c.get("base attack bonus")
        c.set("touch attack", bab + c.get("strength bonus"))
        c.set("ranged touch attack", bab + c.get("dexterity bonus"))

        return c

    def importCharacters(self, hlXml):
        characters = []

        hlroot = ET.XML(hlXml)
        hlpublic = hlroot.find("public")
        if hlpublic is None:
            raise ParsingException("Not a HeroLab XML schema file?")

        charTrees = hlpublic.findall("character")

        for cTree in charTrees:
            c = self.importCharacter(cTree)
            characters.append(c)

        return characters

class HeroLab5eImporter(HeroLabPfImporter):
    def ability(self, tag):
        name = tag.get("name").lower()
        base = int(tag.find("abilvalue").get("base"))
        modified = int(tag.find("abilvalue").get("modified"))
        bonus = int(tag.find("abilbonus").get("modified"))
        save = int(tag.find("savingthrow").get("text"))

        return {
            "{}".format(name): modified,
            "base {}".format(name): base,
            "{} bonus".format(name): bonus,
            "{} save".format(name): save,
        }

    def abilityScores(self, charET):
        abilities = {}
        for a in charET.find("abilityscores"):
            abilities.update(self.ability(a))

        return abilities

    def gold(self, charET):
        money = charET.find("money")

        gp = 0

        for coin in money:
            if coin.get("abbreviation") in coinValues:
                gp += coinValues[coin.get("abbreviation")] * int(coin.get("count"))
            else:
                raise ParsingException("Unknown coin type {}".format(coin.get("abbreviation")))

        return gp

    def skill(self, s):
        name = s.get("name")
        value = int(s.get("value"))

        skill = {
            "name": name,
            "value:": value,
            "ability": abbreviations[s.get("abilabbreviation").lower().capitalize()],
            "ability bonus": int(s.get("abilbonus")),
            "proficent": isStrBoolTrue(s.get("isproficient", "no"))
        }
        return skill

    def createAttack(self, attackData):
        a = attack.Attack(attackData["name"])
        a.bonus = attack.attackBonus(attackData["attack"])
        a.damageText = attackData["damage"]
        a.damageRoll = attack.getDamageRoll(attackData["damage"])
        a.quantity = attackData.get("quantity")

        critRange = (20, 2)
        #a.criticalRange = critRange[0]
        #a.criticalMultiplier = critRange[1]

        #a.category = attackData.get("category")
        #a.equipped = attackData.get("equipped")
        a.damageType = attackData.get("typetext")

        return a

    def encumbrance(self, charET):
        encumberET = charET.find("encumbrance")
        return {
            "encumbrance" : tryToConvertValue(encumberET.get("carried")),
            "max encumbrance": tryToConvertValue(encumberET.get("max"))
        }

    def importCharacter(self, charET):
        #charET = charTrees.pop()

        c = character.Character(charET.get("name"))
        #characters.append(c)

        #minions = charET.find("minions").findall("character")
        #charTrees.extend(minions)

        c.set("name", c.name)
        c.set("race", charET.find("race").get("displayname"))
        c.set("size", charET.find("size").get("name"))
        c.set("alignment", charET.find("alignment").get("name"))
        c.set("deity", charET.find("deity").get("name"))
        c.set("xp", charET.find("xp").get("total"))
        c.set("size", charET.find("size").get("name"))
        #c.set("cr", tryToConvertValue(charET.find("challengerating").get("value")))
        #c.set("base attack bonus", tryToConvertValue(charET.find("attack").get("baseattack")))

        c.stats.update(self.personal(charET))
#        c.stats.update(self.maneuvers(charET))
        c.stats.update(self.encumbrance(charET))

        c.stats.update(self.health(charET))
        #self.classes(c, charET)
        c.set("gold", self.gold(charET))
        c.set("languages", self.languages(charET))
        c.stats.update(self.abilityScores(charET))
        #c.stats.update(self.saves(charET))
        c.set("ac", charET.find("armorclass").get("ac"))
        c.set("initiative", self.initiative(c, charET))
        c.set("speed", self.movementSpeed(charET))
        c.stats.update(self.skills(c, charET))
        c.set("feats", self.feats(charET))
        self.items(c, charET)
        self.attacks(c, charET)
        c.trackedResources = self.trackedResources(charET)

        #bab = c.get("base attack bonus")
        #c.set("touch attack", bab + c.get("strength bonus"))
        #c.set("ranged touch attack", bab + c.get("dexterity bonus"))

        return c


if __name__ == "__main__":
    file = "/Users/troldrik/Desktop/Galdrin.xml"
    #file = "/Users/troldrik/Desktop/party.xml"

    with open(file, encoding="utf-8") as f:
        xml = f.read()

    hl = HeroLab5eImporter()
    chars = hl.importCharacters(xml)

    print(chars[1].trackedResources)