###
# coding: utf-8
# Copyright (c) 2014, Henrik Sørensen
# All rights reserved.
#
#
###

from supybot.test import *

class PathfinderTestCase(PluginTestCase):
    plugins = ('Pathfinder',)

    def testRoll(self):
        self.assertNotError("roll d20")
        self.assertNotError("roll 20")
        self.assertNotError("roll mordy will")
        self.assertNotError("roll mordy will +2")
        self.assertNotError("roll mordy will +2 vs 12")
        self.assertNotError("roll d20 + 2 vs janef touch ac")

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
