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

            for each in spellCasters:
                # filter out spells not from this class.
                spellList = getSpells(spontaneous, charET)
                spellList = filter(lambda sp: sp[0].lower() == each.casterClass.lower(), spellList)
                spellList = list(map(toCastableSpell, spellList))

                each.assignSpells(spellList)

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

def gold(charET):
    money = charET.find("money")
    gp = getGoldValue(int(money.get("pp")), int(money.get("gp")), int(money.get("sp")), int(money.get("cp")))
    return gp


def languages(charET):
    languages = []
    for l in charET.find("languages"):
        languages.append(l.get("name"))
    return ', '.join(languages)


def abilityScores(charET):
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

def saves(charET):
    saves = {}
    for s in charET.find("saves"):
        if s.tag == "save":
            name = s.get("name").lower()
            value = int(s.get("save"))
            saves[name] = value
    return saves

def armourClass(charET):
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

def initiative(c, charET):
    init = charET.find("initiative")
    return int(init.get("total"))


def movementSpeed(charET):
    movement = charET.find("movement").find("speed")
    return int(movement.get("value"))


def skills(c, charET):
    skills = {}
    for s in charET.find("skills"):
        if s.tag == "skill":
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
            skills[s.get("name").lower()] = int(s.get("value"))

    return skills

def feats(charET):
    feats = []
    for f in charET.find("feats"):
        if f.tag == "feat":
            feats.append(f.get("name"))
    return ', '.join(feats)


def getSpell(s):
    castsLeft = tryToConvertValue(s.get("castsleft"))
    casterClass = s.get("class").lower()

    # Annoyingly Domain spells seem to get the class="" attribute
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


def health(charET):
    health = charET.find("health")
    return {
        "hp": int(health.get("currenthp")),
        "totalhp": int(health.get("hitpoints"))
    }


def personal(charET):
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
        c.set("base attack bonus", tryToConvertValue(charET.find("attack").get("baseattack")))

        c.stats.update(personal(charET))
        c.set("resistance", getListOfAttributes("shortname", charET.find("resistances").findall("special")))
        c.set("dr", getListOfAttributes("shortname", charET.find("damagereduction").findall("special")))
        c.set("immunity", getListOfAttributes("shortname", charET.find("immunities").findall("special")))
        c.stats.update(maneuvers(charET))
        c.stats.update(encumbrance(charET))

        c.stats.update(health(charET))
        classes(c, charET)
        c.set("gold", gold(charET))
        c.set("languages", languages(charET))
        c.stats.update(abilityScores(charET))
        c.stats.update(saves(charET))
        c.stats.update(armourClass(charET))
        c.set("initiative", initiative(c, charET))
        c.set("speed", movementSpeed(charET))
        c.stats.update(skills(c, charET))
        c.set("feats", feats(charET))
        items(c, charET)
        attacks(c, charET)
        dailyUse(c, charET)

        bab = c.get("base attack bonus")
        c.set("touch attack", bab + c.get("strength bonus"))
        c.set("ranged touch attack", bab + c.get("dexterity bonus"))

    return characters

