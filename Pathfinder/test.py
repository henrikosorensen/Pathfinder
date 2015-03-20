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


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
