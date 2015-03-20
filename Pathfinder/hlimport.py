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

def getGoldValue(pp, gp, sp, cp):
    return (pp * 10) + gp + sp / 10.0 + cp / 100.0

def cloneAttributes(e):
    d = {}
    for key, value in e.items():
        value = tryToConvertValue(value)
        d[key] = value

    return d

def getClass(classET, charET):
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
            sc = spellclass(sc)

            baseSpellDC = int(classET.get("basespelldc", 10))
            casterLevel = int(classET.get("casterlevel", 0))
            concentrationCheck = int(classET.get("concentrationcheck", 0))
            overcomeSR = int(classET.get("overcomespellresistance"))
            source = classET.get("castersource")

            spontaneous = sc["spontaneous"]
            max = sc["max"]
            used = sc["used"]

            def toCastableSpell(tuple):
                className, castsLeft, s = tuple
                spellLevel = s.level

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


            spellList = getSpells(spontaneous, charET)
            # filter out spells not from this class. Annoyingly Domains seem to get the class="" attribute
            spellList = filter(lambda sp: sp[0].lower() == charClass.name.lower(), spellList)
            spellList = list(map(toCastableSpell, spellList))

            if spontaneous:
                spellCaster = spell.SpontaneousCaster(charClass.name, casterLevel, used, max, baseSpellDC, concentrationCheck, overcomeSR, source)
                spellCasters.append(spellCaster)
            else:
                spellCaster = spell.PreparedCaster(charClass.name, casterLevel, max, baseSpellDC, concentrationCheck, overcomeSR, source)
                spellCasters.append(spellCaster)

                domains = getDomains(name, charET)
                if len(domains) > 0:
                    domainSlots = [0] + [1] * (len(max) - 1)
                    domainCaster = spell.PreparedCaster("domain", casterLevel, domainSlots, baseSpellDC, concentrationCheck, overcomeSR, source)
                    spellCasters.append(domainCaster)

            spellCaster.assignSpells(spellList)

            return charClass, spellCasters
        else:
            raise RuntimeError("Cannot find spellclass tag for class {}".format())


def getDomains(fullClassName, charET):
    domains = []
    otherSpecialsET = charET.find("otherspecials")

    for specialET in otherSpecialsET:
        exp = "{} Domain".format(fullClassName)
        if specialET.get("name").startswith(exp):
            domains.append(specialET.get("shortname"))

    return domains

def classes(c, charET):
    classesET = charET.find("classes")
    c.set("level", classesET.get("level"))
    c.set("class", classesET.get("summary"))

    c.classes = {}
    for classET in classesET:
        cl, caster = getClass(classET, charET)
        c.classes[cl.name] = cl

        for each in caster:
            c.spellCaster[each.casterClass] = each

def getSpells(spontaneous, charET):
    spells = []
    for s in charET.find("spellsknown" if spontaneous else "spellsmemorized"):
        spells.append(getSpell(s))

    return spells

def gold(c, charET):
    money = charET.find("money")
    gp = getGoldValue(int(money.get("pp")), int(money.get("gp")), int(money.get("sp")), int(money.get("cp")))
    c.set("gold", gp)


def languages(c, charET):
    languages = []
    for l in charET.find("languages"):
        languages.append(l.get("name"))
        c.set("languages", languages)


def abilityScores(c, charET):
    for a in charET.find("attributes"):
        stat = a.get("name")
        value = int(a.find("attrvalue").get("modified"))
        baseValue = int(a.find("attrvalue").get("base"))
        c.set(stat, value)
        c.set(stat + " bonus", int(a.find("attrbonus").get("modified")))
        c.set("base " + stat, baseValue)


def saves(c, charET):
    for s in charET.find("saves"):
        if s.tag == "save":
            c.set(s.get("name"), int(s.get("save")))


def armourClass(c, charET):
    ac = charET.find("armorclass")
    c.set("AC", ac.get("ac"))
    c.set("touch AC", ac.get("touch"))
    c.set("flatfooted AC", ac.get("flatfooted"))

    penalties = charET.find("penalties")
    for p in penalties:
        if p.get("name") == "Armor Check Penalty":
            c.set("ACP", int(p.get("value")))
        if p.get("name") == "Max Dex Bonus":
            c.set("max dexterity bonus", tryToConvertValue(p.get("value")))


def initiative(c, charET):
    init = charET.find("initiative")
    c.set("initiative", int(init.get("total")))


def movementSpeed(c, charET):
    movement = charET.find("movement").find("speed")
    c.set("speed", int(movement.get("value")))


def skills(c, charET):
    for s in charET.find("skills"):
        if s.tag == "skill":
            c.set(s.get("name"), int(s.get("value")))
            skill = {
                "name": s.get("name"),
                "value:": int(s.get("value")),
                "ability": abbreviations[s.get("attrname").lower().capitalize()],
                "ability bonus": int(s.get("attrbonus")),
                "class skill": isStrBoolTrue(s.get("classskill", "no")),
                "ranks": int(s.get("ranks")),
                "armor check penalty": isStrBoolTrue(s.get("armorcheck", "no"))
            }
            c.skills[skill["name"]] = skill


def feats(c, charET):
    feats = []
    for f in charET.find("feats"):
        if f.tag == "feat":
            feats.append(f.get("name"))
    c.set("feats", ', '.join(feats))


def getSpell(s):
    castsLeft = tryToConvertValue(s.get("castsleft"))
    casterClass = s.get("class").lower()

    # Domain spells get class = "" attribute
    if casterClass == "":
        casterClass = "domain"

    spellData = {
        "name": s.get("name"),
        "dc": tryToConvertValue(s.get("dc")),
        "school": s.get("schooltext"),
        "spellResistance": s.get("resist"),
        "effect": s.get("effect", ''),
        "castingTime": s.get("casttime"),
        "duration": s.get("duration"),
        "subschool": s.get("subschooltext"),
        "target": s.get("target"),
        "range": s.get("range"),
        "components": s.get("componenttext"),
        "savingThrow": s.get("save"),
        "description": s.find("description").text,
        "spellLevel": "{} {}".format(casterClass, s.get("level")),

        "level": tryToConvertValue(s.get("level")),
        casterClass.lower(): tryToConvertValue(s.get("level"))
    }

    return casterClass, castsLeft, spell.Spell(spellData)


def items(c, charET):
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


def attacks(c, charET):
    rangedAttacks = charET.find("ranged")
    for weapon in rangedAttacks:
        if weapon.tag == "weapon":
            a = cloneAttributes(weapon)
            a = (attack.createFromHeroLab(a))
            c.attacks[a.name] = a
    meleeAttacks = charET.find("melee")
    for weapon in meleeAttacks:
        if weapon.tag == "weapon":
            a = cloneAttributes(weapon)
            a = attack.createFromHeroLab(a)
            c.attacks[a.name] = a


def dailyUse(c, charET):
    trackedResources = charET.find("trackedresources")
    for r in trackedResources:
        if r.get("name").find("/day") != -1:
            du = {
                "name": r.get("name"),
                "used": int(r.get("used")),
                "max": int(r.get("max"))
            }
            c.dailyUse[du["name"]] = du

def spellclass(sc):
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


def health(c, charET):
    health = charET.find("health")
    c.set("totalhp", int(health.get("hitpoints")))
    c.set("hp", int(health.get("currenthp")))


def personal(charET):
    personalData = charET.find("personal")
    p = {
        "gender": personalData.get("gender"),
        "age": tryToConvertValue(personalData.get("age")),
        "hair": personalData.get("hair"),
        "eyes": personalData.get("eyes"),
        "skin": personalData.get("skin"),
        "weight": tryToConvertValue(personalData.find("charweight").get("value")),
        "height": personalData.find("charheight").get("text")
    }

    return p


def getListOfAttributes(attribute, tags):
    attributes = []

    for tag in tags:
        attributes.append(tag.get(attribute))

    return ', '.join(attributes)

def resistance(charET):
    resistances = []

    resistanceET = charET.find(resistances)

    for r in resistanceET.findall("special"):
        resistances.append(r.get("shortname"))

def maneuvers(charET):
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

def encumbrance(charET):
    encumberET = charET.find("encumbrance")
    return {
        "emcumbrance" : tryToConvertValue(encumberET.get("carried")),
        "light encumbrance": tryToConvertValue(encumberET.get("light")),
        "medium encumbrance": tryToConvertValue(encumberET.get("medium")),
        "heavy encumbrance": tryToConvertValue(encumberET.get("heavy"))
    }

def importCharacters(hlXml):
    characters = []

    hlroot = ET.XML(hlXml)
    hlpublic = hlroot.find("public")

    charTrees = hlpublic.findall("character")
    while len(charTrees) > 0:
        charET = charTrees.pop()

        c = character.Character(charET.get("name"))
        characters.append(c)

        minions = charET.find("minions").findall("character")
        charTrees.extend(minions)

        c.set("name", c.name)
        c.set("race", charET.find("race").get("name"))
        c.set("size", charET.find("size").get("name"))
        c.set("alignment", charET.find("alignment").get("name"))
        c.set("deity", charET.find("deity").get("name"))
        c.set("xp", charET.find("xp").get("total"))
        c.set("size", charET.find("size").get("name"))
        c.set("cr", tryToConvertValue(charET.find("challengerating").get("value")))

        c.stats.update(personal(charET))
        c.set("resistance", getListOfAttributes("shortname", charET.find("resistances").findall("special")))
        c.set("dr", getListOfAttributes("shortname", charET.find("damagereduction").findall("special")))
        c.set("immunity", getListOfAttributes("shortname", charET.find("immunities").findall("special")))
        c.stats.update(maneuvers(charET))
        c.stats.update(encumbrance(charET))
        c.set("base attack bonus", tryToConvertValue(charET.find("attack").get("baseattack")))

        health(c, charET)
        classes(c, charET)
        gold(c, charET)
        languages(c, charET)
        abilityScores(c, charET)
        saves(c, charET)
        armourClass(c, charET)
        initiative(c, charET)
        movementSpeed(c, charET)
        skills(c, charET)
        feats(c, charET)
        items(c, charET)
        attacks(c, charET)
        dailyUse(c, charET)
        #spells(c, charET)
        #spellclasses(c, charET)

    return characters

