###
# coding: utf-8
# Copyright (c) 2014, Henrik Sørensen
# All rights reserved.
#
#
###

"""
Add a description of the plugin (to be presented to the user inside the wizard)
here.  This should describe *what* the plugin does.
"""
import importlib
import supybot
import supybot.world as world

# Use this for the version of this plugin.  You may wish to put a CVS keyword
# in here if you're keeping the plugin in CVS or some similar system.
__version__ = ""

# XXX Replace this with an appropriate author or supybot.Author instance.
__author__ = supybot.authors.unknown

# This is a dictionary mapping supybot.Author instances to lists of
# contributions.
__contributors__ = {}

# This is a url where the most recent plugin package can be downloaded.
__url__ = '' # 'http://supybot.com/Members/yourname/Pathfinder/download'

from . import config
from . import plugin
importlib.reload(plugin) # In case we're being reloaded.
# try to reload our modules, in case plugin is reloaded.
try:
    importlib.reload(character)
    importlib.reload(hlimport)
    importlib.reload(gamestate)
    importlib.reload(item)
    importlib.reload(rollParser)
    importlib.reload(rollSemantics)
    importlib.reload(attack)
    importlib.reload(util)
    importlib.reload(db)
    importlib.reload(attack)
    importlib.reload(spell)
except NameError:
    pass
# Add more reloads here if you add third-party modules and want them to be
# reloaded when this plugin is reloaded.  Don't forget to import them as well!

if world.testing:
    from . import test

Class = plugin.Class
configure = config.configure


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
