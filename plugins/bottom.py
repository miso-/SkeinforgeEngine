"""
Bottom sets the bottom of the carving to the defined altitude. Adjusts the Z heights of each layer.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from fabmetheus_utilities import archive
from fabmetheus_utilities.vector3 import Vector3
import os
import sys
import time
import math
import logging
from config import config

logger = logging.getLogger(__name__)
name = __name__


def performAction(slicedFile):
    "Align the model to the bottom of the printing plane"

    # HACK these options are in "speed" section so they should be set no matter if bottom plugin is active
    firstLayerFeedRateRatio = config.getfloat('speed', 'feed.rate.first.layer.ratio')
    firstLayerFlowRateRatio = config.getfloat('speed', 'flow.rate.first.layer.ratio')
    for (layer, instance) in slicedFile.printbed.getLayersGroupedByZ()[0]:
        layer.feedAndFlowRateMultiplier = [firstLayerFeedRateRatio, firstLayerFlowRateRatio]

    if not config.getboolean(name, 'active'):
        logger.info("%s plugin is not active", name.capitalize())
        return
    BottomSkein(slicedFile).bottom()


class BottomSkein:
    "A class to bottom a skein of extrusions."

    def __init__(self, slicedFile):
        self.slicedFile = slicedFile
        self.additionalHeightRatio = config.getfloat(name, 'additional.height.ratio')
        self.altitude = config.getfloat(name, 'altitude')
        self.layerHeight = config.getfloat('carve', 'layer.height')
        self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
        self.decimalPlaces = config.getint('general', 'decimal.places')

    def bottom(self):
        '''Adjust bottom layer'''

        zBottoms = []
        for instance in self.slicedFile.printbed.instances:
            zBottoms.append(instance.object.layers[0].z + instance.placement.displacement.z)

        zBottom = min(zBottoms)
        deltaZ = self.altitude + self.additionalHeightRatio * self.layerHeight - zBottom

        for instance in self.slicedFile.printbed.instances:
            instance.placement.displacement += Vector3(0, 0, deltaZ)

        self.slicedFile.printbed.finalize()
