import random
import rollParser

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

def diceRoll(dice, sides, trace):
    total = 0
    rolls = []
    for x in range(0, dice):
        roll = random.randrange(1, sides)
        rolls.append(roll)
        total += roll

    trace.append("%d %s" % (total, rolls))
    return total

def statLookup(gameState, charName, stat, trace):
    value = gameState.getStat(charName, stat)
    if value is None:
        raise LookupError
    #trace.append("%d" % value)
    return value

def versus(a, b, trace):
    trace.append("%d vs %d" % (a, b))
    return a >= b


class ArgSementics(object):
    def __init__(self, dice = 50, sides = 10000):
        self.rolls = []
        self.maxSides = sides
        self.maxDice = dice

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

    def opExpr(self, ast):
        a = ast[0]
        operands = ast[1]
        # If we're not falling through, but actually have an +/- expression, ast[1] should contain our operands
        if len(operands) > 0:
            operands.reverse()

            # Should come in op number pairs
            assert(len(operands) % 2 == 0)
            for i in range(0, len(operands), 2):
                op = operands.pop()
                operand = operands.pop()
                a = (a, operand, op)

        return a

    def rollExpr(self, ast):
        # If the optional vs expr is supplied, we get a list
        if type(ast) is list:
            return (ast[0], ast[2], ast[1])
        # Else we just get our tuples

        return ast


class Roller(object):
    def __init__(self, gameState):
        self.gameState = gameState
        self.trace = []
        self.opCodes = {
            "add": add,
            "sub": sub,
            "roll": diceRoll,
            "lookup": lambda c, s, t : statLookup(self.gameState, c, s, t),
            "vs": versus
        }
        self.semantics = ArgSementics()
        self.argParser = roll.rollParser(parseinfo=True, semantics = self.semantics)

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