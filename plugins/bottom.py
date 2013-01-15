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
import os, sys, time, math, logging
from config import config

logger = logging.getLogger(__name__)
name = __name__

def performAction(slicedModel):
    "Align the model to the bottom of the printing plane"

    # HACK these options are in "speed" section so they should be set no matter if bottom plugin is active
    firstLayerFeedRateRatio = config.getfloat('speed', 'feed.rate.first.layer.ratio')
    firstLayerFlowRateRatio = config.getfloat('speed', 'flow.rate.first.layer.ratio')
    slicedModel.layers[0].feedAndFlowRateMultiplier = [firstLayerFeedRateRatio, firstLayerFlowRateRatio]

    if not config.getboolean(name, 'active'):
        logger.info("%s plugin is not active", name.capitalize())
        return
    BottomSkein(slicedModel).bottom()

class BottomSkein:
    "A class to bottom a skein of extrusions."
    def __init__(self, slicedModel):
        self.slicedModel = slicedModel
        self.additionalHeightRatio = config.getfloat(name, 'additional.height.ratio')
        self.altitude = config.getfloat(name, 'altitude')
        self.layerHeight = config.getfloat('carve', 'layer.height')
        self.perimeterWidth = config.getfloat('carve', 'extrusion.width')
        self.decimalPlaces = config.getint('general', 'decimal.places')

    def bottom(self):
        '''Adjust bottom layer'''
        zBottom = self.slicedModel.layers[0].z
        deltaZ = self.altitude + self.additionalHeightRatio * self.layerHeight - zBottom

        self.slicedModel.shiftLayers(deltaZ)
