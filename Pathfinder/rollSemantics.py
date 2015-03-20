if __package__ != '':
    from . import rollParser
else:
    import rollParser
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

    return (total, "%d %s" % (total, rolls), "annotate")

def statLookup(gameState, charName, stat):
    value = gameState.getStat(charName, stat)
    if value is None:
        raise LookupError("Unknown Character or Stat")
    
    charName = value[2].name
    statName = value[0]
    statValue = value[1]
    
    return (statValue, "%d (%s's %s)" % (statValue, charName, statName), "annotate")

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
        if type(ast) is tuple:
            return ast
        
        right = ast.pop()
        op = ast.pop()
        left = ast.pop()

        return (left, right, op)

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
            ability += " " + " ".join(ast[1])
        
        return ability

    def abilityLookup(self, ast):
        charname = ast[0]
        ability = ast[1]
        lookup = (charname, ability, "lookup")

        return lookup

    def rollAbility(self, ast):
        rightSide = ast.pop()

        opCode = ast.pop()
        assert opCode == 'vs'

        leftAddon = ast.pop()
        leftSide = ast.pop()

        leftSide = self.__getExpressionsFromList(leftSide, leftAddon)
        roll = (1, self.abilityDice, "roll")
        leftSide = (roll, leftSide, "add")


        return (leftSide, rightSide, opCode)



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

    def __str__(self):
        return self.symbol

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

        return self.__expressionWalk(evaluate, asg), self.exprToInfix(asg, [])

    def doRoll(self, text):
        asg = self.parseRoll(text)
        return self.execute(asg)

    def parseAttackRoll(self, text):
        asg = self.argParser.parse(text, "attackRoll", whitespace=None)
        return asg

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
                return "(%s %s %s)" % (left, op.symbol, right)
            else:
                return "%s %s %s" % (left, op.symbol, right)

        else:
            return right
