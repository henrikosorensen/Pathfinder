from character import Character
import xml.etree.ElementTree as ET

def importCharacters(hlXml):
    hlroot = ET.XML(hlXml)


    hlpublic = hlroot.find("public")

    characters = []

    charTrees =hlpublic.findall("character")
    while len(charTrees) > 0:
        charET = charTrees.pop()

        c = Character(charET.get("name"))
        characters.append(c)

        minions = charET.find("minions").findall("character")
        charTrees.extend(minions)

        c.set("name", c.name)
        c.set("race", charET.find("race").get("name"))
        c.set("size", charET.find("size").get("name"))
        c.set("alignment", charET.find("alignment").get("name"))
        c.set("deity", charET.find("deity").get("name"))
        c.set("xp", charET.find("xp").get("total"))

        health = charET.find("health")
        c.set("totalhp", int(health.get("hitpoints")))
        c.set("hp", int(health.get("currenthp")))

        cls = charET.find("classes")
        c.set("level", cls.get("level"))
        c.set("class", cls.get("summary"))
        for cl in cls:
            c.classes.append({
                "name": cl.get("name"),
                "level": cl.get("level"),
                "spells": cl.get("spells"),
                "casterlevel": cl.get("casterlevel"),
                "concentrationcheck": cl.get("concentrationcheck"),
                "overcomespellresistance": cl.get("overcomespellresistance"),
                "basespelldc": cl.get("basespelldc"),
                "castersource": cl.get("castersource")
            })

        money = charET.find("money")
        gold = int(money.get("pp")) * 10 + int(money.get("gp")) + int(money.get("sp")) / 10 + int(money.get("cp")) / 100
        c.set("gold", gold)

        languages = []
        for l in charET.find("languages"):
            languages.append(l.get("name"))
            c.set("languages", languages)

        for a in charET.find("attributes"):
            stat = a.get("name")
            value = int(a.find("attrvalue").get("modified"))
            c.set(stat, value)
            c.set(stat + " bonus", int(a.find("attrbonus").get("modified")))

        for s in charET.find("saves"):
            if s.tag == "save":
                c.set(s.get("name"), int(s.get("save")))

        ac = charET.find("armorclass")
        c.set("AC", ac.get("ac"))
        c.set("touch AC", ac.get("touch"))
        c.set("flatfooted AC", ac.get("flatfooted"))

        penalties = charET.find("penalties")
        for p in penalties:
            if p.get("name") == "Armor Check Penalty":
                c.set("ACP", int(p.get("value")))

        init = charET.find("initiative")
        c.set("initiative", int(init.get("total")))
        movement = charET.find("movement").find("speed")
        c.set("speed", int(movement.get("value")))

        for s in charET.find("skills"):
            if s.tag == "skill":
                c.set(s.get("name"), int(s.get("value")))
                c.skills.append((s.get("name"), s.get("value")))

        feats = []
        for f in charET.find("feats"):
            if f.tag == "feat":
                feats.append(f.get("name"))
        c.set("feats", feats)

        classes = charET.find("classes")

        spells = charET.find("spellsknown")
        spells.extend(charET.find("spellsmemorized"))
        for s in spells:
            spell = s.attrib.copy()
            c.spells.append(spell)


        rangedAttacks = charET.find("ranged")
        for weapon in rangedAttacks:
            if weapon.tag == "weapon":
                attack = {
                    "name" : weapon.get("name"),
                    "damage" : weapon.get("damage"),
                    "bonus" : weapon.get("attack"),
                    "type": weapon.get("typetext"),
                    "critical": weapon.get("crit")
                }
                c.attacks.append(attack)

        meleeAttacks = charET.find("melee")
        for weapon in meleeAttacks:
            if weapon.tag == "weapon":
                attack = {
                    "name" : weapon.get("name"),
                    "damage" : weapon.get("damage"),
                    "bonus" : weapon.get("attack"),
                    "type": weapon.get("typetext"),
                    "critical": weapon.get("crit")
                }
                c.attacks.append(attack)

        trackedResources = charET.find("trackedresources")
        for r in trackedResources:
            if r.get("name").find("/day") != -1:
                c.dailyUse.append({
                    "name": r.get("name"),
                    "used": int(r.get("used")),
                    "max": int(r.get("max"))
                })

        spellclasses = charET.find("spellclasses")
        for sc in spellclasses:
            if sc.get("spells").lower() == "spontaneous":
                for sl in sc:
                    if not sl.get("unlimited"):
                        spellLevel = {
                            "name": "Level %s %sspells" % (sl.get("level"), sc.get("name") + " " if len(spellclasses) > 1 else ""),
                            "level": int(sl.get("level")),
                            "used": int(sl.get("used")),
                            "max": int(sl.get("maxcasts")),
                            "class": sc.get("class")
                        }
                        c.dailyUse.append(spellLevel)


    return characters

