import rollParser
import string

class ValueToLargeError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def add(a, b, trace):
    #trace.append("+ %d" % b)
    return a + b

def sub(a, b, trace):
    #trace.append("- %d" % b)
    return a - b

def mul(a, b, trace):
    #trace.append("* %d", b)
    return a * b

def div(a, b, trace):
    #trace.append("/ %d", b)
    return a / b

def diceRoll(random, dice, sides, trace):
    total = 0
    rolls = []
    for x in range(0, dice):
        roll = random.randrange(1, sides)
        rolls.append(roll)
        total += roll

    trace.append("%s" % rolls)
    return total

def statLookup(gameState, charName, stat, trace):
    value = gameState.getStat(charName, stat)
    if value is None:
        raise LookupError("Unknown Character or Stat")
    
    charName = value[2].name
    statName = value[0]
    statValue = value[1]
    
    trace.append("%s's %s %d" % (charName, statName, statValue))
    return statValue

def versus(a, b, trace):
    trace.append("%d vs %d" % (a, b))
    return a >= b


class ArgSementics(object):
    def __init__(self, dice = 50, sides = 10000, abilityDice = 20):
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

    def sides(self, ast):
        if ast > self.maxSides:
            raise ValueToLargeError("Maximum die sides is %d" % self.maxSides)
        return ast

    def diceCount(self, ast):
        if ast > self.maxDice:
            raise ValueToLargeError("Maximum dice is %d" % self.maxDice)
        return ast

    def sum(self, ast):
        return self.opExpr(ast)

    def product(self, ast):
        return self.opExpr(ast)

    def rollExpr(self, ast):
        # If the optional vs expr is supplied, we get a list
        if type(ast) is list:
            return (ast[0], ast[2], ast[1])
        # Else we just get our tuples
        return ast

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

    def ability(self, ast):
        ability = ast[0]
        if len(ast[1]) > 0:
            ability += " " + string.join(ast[1])

        return ability

    def abilityLookup(self, ast):
        charname = ast[0]
        ability = ast[1]
        lookup = (charname, ability, "lookup")
        roll = (1, self.abilityDice, "roll")

        return (lookup, roll, "add")

    def rollAbility(self, ast):
        expression = self.__getExpressionsFromList(ast[0], ast[1])

        # If there's a vs expression
        if len(ast) > 2:
            expression = (expression, ast[3], ast[2])

        return expression

class Roller(object):
    def __init__(self, gameState, rng):
        self.gameState = gameState
        self.rng = rng
        self.trace = []
        self.opCodes = {
            "add": add,
            "sub": sub,
            "roll": lambda d, s, t : diceRoll(self.rng, d, s, t),
            "lookup": lambda c, s, t : statLookup(self.gameState, c, s, t),
            "vs": versus,
            "mul": mul,
            "div": div
        }
        self.semantics = ArgSementics()
        self.argParser = rollParser.rollParser(parseinfo=True, semantics = self.semantics)

    def __evaluate(self, asg):
        if type(asg) is not tuple:
            return asg

        a = self.__evaluate(asg[0])
        b = self.__evaluate(asg[1])
        opCode = asg[2]
        op = self.opCodes[opCode]

        return op(a, b, self.trace)

    def parseRoll(self, text):
        asg = self.argParser.parse(text, "roll", whitespace=None)
        return asg

    def execute(self, asg):
        self.trace = []

        return (self.__evaluate(asg), self.trace)

    def doRoll(self, text):
        asg = self.parseRoll(text)
        return self.execute(asg)
