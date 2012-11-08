"""
Support adds layers for supporting overhangs.
Extracted from the Skeinforge raft plugin.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from importlib import import_module
import logging
import os
import sys

name = __name__
logger = logging.getLogger(name)

def performAction(slicedModel):
    "Add support layers."
    if not config.getboolean(name, 'active'):
        logger.info("%s plugin is not active", name.capitalize())
        return

    supportStrategy = None
    supportStrategyName = config.get(name, 'strategy')
    supportStrategyPath = config.get(name, 'strategy.path')

    try:
        if supportStrategyPath not in sys.path:
            sys.path.insert(0, supportStrategyPath)
        supportStrategy = import_module(supportStrategyName).getStrategy(slicedModel)
        logger.info("Using support strategy: %s", supportStrategyName)
    except ImportError:
        logger.warning("Could not find module for fill strategy called: %s", supportStrategyName)
    except Exception as inst:
        logger.warning("Exception reading strategy %s: %s", supportStrategyName, inst)


    supportStrategy.support()
