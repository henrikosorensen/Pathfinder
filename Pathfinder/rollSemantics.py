import rollParser
import string
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
        roll = random.randrange(1, sides)
        rolls.append(roll)
        total += roll

    return (total, "%d %s" % (total, rolls), "annotate")

def statLookup(gameState, charName, stat, trace):
    value = gameState.getStat(charName, stat)
    if value is None:
        raise LookupError("Unknown Character or Stat")
    
    charName = value[2].name
    statName = value[0]
    statValue = value[1]
    
    return (statValue, "%s's %s is %d" % (charName, statName, statValue), "annotate")

def versus(a, b):
    return a >= b

def annotate(a, b):
    return a

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
        # If the optional vs expr is supplied, we get a list of tuples
        if type(ast) is list:
            return ast[0] + ast[1]
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
            expression = expression + ast[2]

        return expression

    def versusExpr(self, ast):
        #ignore optional string arg
        return (ast[-1], ast[0])

    def attackRoll(self, ast):
        print ast
        return ast

class OperatorPrecedence(enum.IntEnum):
    annotate = 5,
    lookup = 4,
    roll = 4,
    mul = 3,
    div = 3,
    add = 2,
    sub = 2,
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

class Roller(object):
    def __init__(self, gameState, rng):
        self.gameState = gameState
        self.rng = rng
        self.trace = []
        self.opTable = {
            "add": Operator(2, '+', "add", add),
            "sub": Operator(2, '-', "sub", sub),
            "mul": Operator(2, '*', "mul", mul),
            "div": Operator(2, '/', "div", div),
            "roll": Operator(2, "roll", "roll", lambda d, s : diceRoll(self.rng, d, s)),
            "lookup": Operator(2, "lookup", "lookup", lambda c, s : statLookup(self.gameState, c, s)),
            "vs": Operator(2, "vs", "vs", versus),
            "annotate": Operator(2, "annotate", "annotate", annotate)
        }
        self.semantics = ArgSementics()
        self.argParser = rollParser.rollParser(parseinfo = True, semantics = self.semantics)

    def getOp(self, opCode):
        return self.opTable[opCode]

    def __evaluate(self, left, right, opCode):
        op = self.getOp(opCode)
        return op.execute(left, right)

    def __expressionWalk(self, visit, asg):
        if type(asg) is not tuple:
            return asg
        else:
            left = self.__expressionWalk(visit, asg[0])
            right = self.__expressionWalk(visit, asg[1])
            opCode = asg[2]

            return visit(left, right, opCode)

    def __preprocess(self, left, right, opCode):
        if opCode == "roll" or opCode == "lookup":
            return self.__evaluate(left, right, opCode)
        else:
            return (left, right, opCode)

    def parseRoll(self, text):
        asg = self.argParser.parse(text, "roll", whitespace=None)
        return asg

    def execute(self, asg):
        evaluate = lambda a, b, opCode : self.getOp(opCode).execute(a, b)
        preprocess = lambda a, b, opCode : evaluate(a, b, opCode) if opCode == "roll" or opCode == "lookup" else (a, b, opCode)

        asg = self.__expressionWalk(preprocess, asg)

        return self.__expressionWalk(evaluate, asg), ' '.join(self.exprToInfix(asg))

    def doRoll(self, text):
        asg = self.parseRoll(text)
        return self.execute(asg)

    def parseAttackRoll(self, text):
        asg = self.argParser.parse(text, "attackRoll", whitespace=None)
        return asg

    def exprToInfix(self, expr):

        if type(expr) is not tuple:
            return [expr.__str__()]

        left = self.exprToInfix(expr[0])
        right = self.exprToInfix(expr[1])
        op = self.getOp(expr[2])

        if op.code != "annotate":
            r = left[:]
            r.append(op.symbol)
            r.extend(right)
            return r

        else:
            return right