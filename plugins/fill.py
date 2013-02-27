"""
Fills the perimeters.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from importlib import import_module
from utilities import memory_tracker
import logging
import math
import sys

logger = logging.getLogger(__name__)
name = __name__


def performAction(slicedFile):
    'Fills the perimeters.'
    if not config.getboolean(name, 'active'):
        logger.info("%s plugin is inactive", name.capitalize())
        return

    f = FillSkein(slicedFile)
    if slicedFile.runtimeParameters.profileMemory:
        memory_tracker.track_object(f)
    f.fill()
    if slicedFile.runtimeParameters.profileMemory:
        memory_tracker.create_snapshot("After fill")


class FillSkein:
    'A class to fill a skein of extrusions.'

    def __init__(self, slicedFile):
        self.slicedFile = slicedFile
        self.extrusionWidth = config.getfloat('carve', 'extrusion.width')
        self.fillStrategyName = config.get(name, 'strategy')
        self.fillStrategyPath = config.get(name, 'strategy.path')

    def fill(self):
        'Fills the layers.'
        if self.extrusionWidth is None:
            logger.warning('Nothing will be done because extrusion width FillSkein is None.')
            return

        fillStrategy = None
        try:
            if self.fillStrategyPath not in sys.path:
                sys.path.insert(0, self.fillStrategyPath)
            fillStrategy = import_module(self.fillStrategyName).getStrategy(self.slicedFile)
            logger.info("Using fill strategy: %s", self.fillStrategyName)
        except ImportError:
            logger.warning("Could not find module for fill strategy called: %s", self.fillStrategyName)
        except Exception as inst:
            logger.warning("Exception reading strategy %s: %s", self.fillStrategyName, inst)

        for object in self.slicedFile.getObjectListToSlice():
            for volume in object.volumes:
                for layer in volume.layers:
                    if fillStrategy is not None:
                        fillStrategy.fill(layer, volume)
