if __package__ != '':
    from . import rollParser
    from . import attack
else:
    import rollParser
    import attack
import enum

class ValueToLargeError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class NoDiceInRollError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

def add(a, b):
    return a + b

def sub(a, b):
    return a - b

def mul(a, b):
    return a * b

def div(a, b):
    return a / b

def diceRoll(random, dice, sides):
    total = 0
    rolls = []
    for x in range(0, dice):
        roll = random.randint(1, sides)
        rolls.append(roll)
        total += roll

    return total, "{} {}".format(total, rolls), "annotate"

def statLookup(gameState, charName, stat):
    c = gameState.findChar(charName)
    if c is None:
        raise LookupError("Unknown Character")

    value = c.getStat(stat)
    if value is None:
        raise LookupError("Unknown Stat")

    statName = value[0]
    statValue = value[1]

    return statValue, "{} ({}'s {})".format(statValue, c.name, statName), "annotate"

def attackLookup(gameState, charName, attackName):
    c = gameState.findChar(charName)
    if c is None:
        raise LookupError("Unknown Character")

    a = c.getAttack(attackName)
    if a is None:
        raise LookupError("Unknown attack {1} on {0}".format(c.name, attackName))

    return c.name, a

def versus(a, b):
    return a >= b

def annotate(a, b):
    return a

class ArgSementics(object):
    def __init__(self, dice = 64, sides = 65536, abilityDice = 20):
        self.rolls = []
        self.maxSides = sides
        self.maxDice = dice
        self.abilityDice = abilityDice

    def _default(self, ast):
        return ast

    def diceRoll(self, ast):
        if (ast[0] == "d"):
            ast.insert(0, 1)

        return ast[0], ast[2], "roll"

    def opAdd(self, ast):
        return "add"

    def opSub(self, ast):
        return "sub"

    def opMul(self, ast):
        return "mul"

    def opDiv(self, ast):
        return "div"

    def opVersus(self, ast):
        return "vs"

    def number(self, ast):
        return int(ast)

    def quotedString(self, ast):
        return ast[1]

    def sides(self, ast):
        if ast > self.maxSides:
            raise ValueToLargeError("Maximum die sides is %d" % self.maxSides)
        return ast

    def diceCount(self, ast):
        if ast > self.maxDice:
            raise ValueToLargeError("Maximum dice is %d" % self.maxDice)
        return ast

    def atom(self, ast):
        # '(' expr ')'
        if type(ast) is list:
            return ast[1]
        else:
            return ast

    def sum(self, ast):
        return self.opExpr(ast)

    def product(self, ast):
        return self.opExpr(ast)

    def rollExpr(self, ast):
        if type(ast) is not list:
            return ast

        left = ast.pop(0)
        op = ast.pop(0)
        right = ast.pop(0)

        return left, right, op

    def __getExpressionsFromList(self, expression, argsList):
        if len(argsList) > 0:
            argsList.reverse()

            assert(len(argsList) % 2 == 0)
            for i in range(0, len(argsList), 2):
                opCode = argsList.pop()
                rValue = argsList.pop()
                expression = (expression, rValue, opCode)

        return expression

    def opExpr(self, ast):
        # If we're not falling through, but actually have an +/- expression, ast[1] should contain our operands
        lValue = ast[0]
        rValue = ast[1]

        return self.__getExpressionsFromList(lValue, rValue)

    def spacedNotVsString(self, ast):
        return ' '.join([ast[0]] + ast[1])

    def ability(self, ast):
        return ast

    def abilityLookup(self, ast):
        charname = ast[0]
        ability = ast[1]
        lookup = (charname, ability, "lookup")

        return lookup

    def rollAbility(self, ast):
        left = ast.pop(0)
        leftAddon = ast.pop(0)
        left = self.__getExpressionsFromList(left, leftAddon)

        roll = (1, self.abilityDice, "roll")
        left = (roll, left, "add")

        if len(ast) > 0:
            right = ast.pop()
            opCode = ast.pop()
            assert opCode == "vs"

            return left, right, opCode

        return left

    def attackLookup(self, ast):
        char = ast[0]
        attackName = ast[1]

        return char, attackName

    def modifiers(self, ast):
        # Not sure why rule is invoked when its not matched....
        if ast is None:
            return (None, None)
        if type(ast) is tuple:
            return ast, None
        assert(type(ast) is list)

        attackBonus = None if ast[0] == ',' else ast[0]
        damageBonus = ast[-1]

        return attackBonus, damageBonus

    def bonus(self, ast):
        if type(ast) is list:
            return ast[1], ast[0]
        return ast, "add"

    def vsExpr(self, ast):
        right = ast[1]
        return right

    def attackRoll(self, ast):
        attack = ast[0]
        bonuses = ast[1] if len(ast) > 1 else (None, None)
        ac = ast[2] if len(ast) > 2 else None

        return attack, bonuses, ac

class OperatorPrecedence(enum.IntEnum):
    annotate = 5
    attackLookup = 4
    lookup = 4
    roll = 4
    mul = 3
    div = 3
    add = 2
    sub = 2
    vs = 1

class Operator(object):
    def __init__(self, arity, symbol, code, eval):
        self.arity = arity
        self.symbol = symbol
        self.eval = eval
        self.code = code
        self.precedence = OperatorPrecedence[code]

    def execute(self, *args):
        if len(args) != self.arity:
            raise RuntimeError("Incorrect number of arguments for %s operator" % self.symbol)

        return self.eval(*args)

    def __str__(self):
        return self.symbol

class Roller(object):
    def __init__(self, gameState, rng):
        self.gameState = gameState
        self.rng = rng
        self.trace = []
        self.opTable = {
            "add": Operator(2, ' + ', "add", add),
            "sub": Operator(2, ' - ', "sub", sub),
            "mul": Operator(2, ' * ', "mul", mul),
            "div": Operator(2, ' / ', "div", div),
            "roll": Operator(2, "d", "roll", lambda d, s: diceRoll(self.rng, d, s)),
            "lookup": Operator(2, " lookup ", "lookup", lambda c, s: statLookup(self.gameState, c, s)),
            "vs": Operator(2, " vs ", "vs", versus),
            "annotate": Operator(2, " annotate ", "annotate", annotate)
        }
        self.semantics = ArgSementics()
        self.argParser = rollParser.rollParser(parseinfo = True, semantics = self.semantics)
        self.preprocessOps = ["roll", "lookup"]

    def getOp(self, opCode):
        return self.opTable[opCode]

    def __expressionWalk(self, visit, asg):
        if type(asg) is not tuple:
            return asg
        else:
            left = self.__expressionWalk(visit, asg[0])
            right = self.__expressionWalk(visit, asg[1])
            opCode = asg[2]

            return visit(left, right, opCode)

    def parseRoll(self, text):
        asg = self.argParser.parse(text, "roll", whitespace=None)
        return asg

    def preprocess(self, expr):
        preprocess = lambda a, b, opCode: self.getOp(opCode).execute(a, b) if opCode in self.preprocessOps else (a, b, opCode)
        return self.__expressionWalk(preprocess, expr)

    def execute(self, expr):
        evaluate = lambda a, b, opCode: self.getOp(opCode).execute(a, b)

        expr = self.preprocess(expr)

        return self.__expressionWalk(evaluate, expr), self.exprToInfix(expr, [])

    def doRoll(self, text):
        expr = self.parseRoll(text)
        return self.execute(expr)

    def exprToInfix(self, expr, opStack):
        if type(expr) is not tuple:
            return expr.__str__()

        op = self.getOp(expr[2])
        opStack.append(op)

        left = self.exprToInfix(expr[0], opStack)
        right = self.exprToInfix(expr[1], opStack)

        if op.code != "annotate":
            currentOp = opStack.pop()
            if opStack != [] and currentOp.precedence < opStack[0].precedence:
                return "({}{}{})".format(left, op.symbol, right)
            else:
                return "{}{}{}".format(left, op.symbol, right)

        else:
            return right

class AttackAction(enum.Enum):
    attackRoll = 1
    critConfirmationRoll = 2
    damageRoll = 3

def mergeExpressions(leftExpr, rightExpr, glueOp):
    # trivial case
    if type(rightExpr) is not tuple:
        return leftExpr, rightExpr, glueOp

    stack = []

    # Traverse down left leaves of the rightExpr
    expr = rightExpr
    while type(expr) is tuple:
        stack.append(expr)
        expr = expr[0]

    # We've hit the buttom of rightExpr, start building merged version.
    e = stack.pop()
    mergedExpr = leftExpr, e, glueOp
    while len(stack) > 0:
        e = stack.pop()

        rVal = e[1]
        op = e[2]
        mergedExpr = mergedExpr, rVal, op

    return mergedExpr

class AttackRoller(Roller):
    def __init__(self, gameState, rng, attackDie = 20):
        super().__init__(gameState, rng)

        self.attackDie = attackDie

    def parseAttackRoll(self, text):
        asg = self.argParser.parse(text, "attackRoll", whitespace=None)
        return asg

    def attackRoll(self, attackBonus, attackAdjustment, acExpr):
        roll = self.opTable["roll"].execute(1, self.attackDie)
        dieCast = roll[0]

        roll = (roll, attackBonus, "add")

        if attackAdjustment is not None:
            roll = mergeExpressions(roll, attackAdjustment[0], attackAdjustment[1])

        result = self.execute(roll)

        if acExpr is not None:
            ac = self.execute(acExpr)
            result = result[0], "{} vs {}".format(result[1], ac[1])
        else:
            ac = None
            #roll = (roll, acExpr, "vs")


        if dieCast == 1:
            hit = False
        elif dieCast == 20:
            hit = True
        elif acExpr is not None:
            hit = result[0] >= ac[0]
        else:
            hit = None

        return {
            "roll": dieCast,
            "total": result[0],
            "trace": result[1],
            "hit": hit,
            "ac": None if ac is None else ac[0]
        }

    def damageRoll(self, attack, damageAdjustmentExpr, crit):
        damageExpr = self.parseRoll(attack.damageRoll)

        if damageAdjustmentExpr is not None:
            damageExpr = mergeExpressions(damageExpr, damageAdjustmentExpr[0], damageAdjustmentExpr[1])

        damage = 0
        trace = []
        multiplier = attack.criticalMultiplier if crit else 1
        for i in range(0, multiplier):
            damageRoll = self.execute(damageExpr)
            damage += damageRoll[0]
            trace.append(damageRoll[1])

        return {
            "damage": damage,
            "damageTrace": ' + '.join(trace)
        }

    def doRoll(self, text, fullAttack = False):
        aLookup, bonuses, acExpr = self.parseAttackRoll(text)

        attacker = aLookup[0]
        try:
            attacker, weapon = attackLookup(self.gameState, aLookup[0], aLookup[1])
        except LookupError as e:
            # Attack lookup failure, if either attack bonus or damage bonus is missing, we can't carry on.
            if None in bonuses:
                raise e
            # We got attack and damage bonuses.... ASSUME these are base values.
            else:
                weapon = attack.Attack(aLookup[1])

                # bonuses are in the form (expr, "add"), strip out the add op
                attackBonusExpr = bonuses[0][0]
                damageBonusExpr = bonuses[1][0]

                # Excute attackBonusExpr to get value
                weapon.bonus = [attackBonusExpr]
                # We need damage in parsable form, use infix converter to transform it back.
                weapon.damageRoll = self.exprToInfix(damageBonusExpr, [])

                bonuses = (None, None)

        attackCount = weapon.getFullAttackCount() if fullAttack else 1

        results = []

        for attackNum in range(0, attackCount):
            weaponBonus = weapon.bonus[attackNum]
            attackAdjustment = bonuses[0]

            result = {
                "attacker": attacker,
                "attack": weapon.name
            }
            result.update(self.attackRoll(weaponBonus, attackAdjustment, acExpr))

            if weapon.inCritRange(result["roll"]) and result["hit"] is not False:
                critResult = self.attackRoll(weaponBonus, attackAdjustment, acExpr)

                result["critical"] = critResult["hit"] is True
                result["criticalTotal"] = critResult["total"]
                result["criticalTrace"] = critResult["trace"]
            else:
                result["critical"] = False

            if result["hit"] is None or result["hit"]:
                result.update(self.damageRoll(weapon, bonuses[1], result["critical"]))

            results.append(result)

        return results