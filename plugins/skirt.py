"""
Adds skirt (extra path) around the object to prime extruder.
Extracted from the Skeinforge skirt plugin.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)
License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import euclidean, intercircle
from fabmetheus_utilities.geometry.solids import triangle_mesh
from entities import SupportPath
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
    SkirtSkein(slicedModel).skirt()

class SkirtSkein:
    'A class to skirt a skein of extrusions.'
    def __init__(self, slicedModel):
        self.slicedModel = slicedModel

        self.convex = config.getboolean(name, 'convex')
        self.gapOverPerimeterWidth = config.getfloat(name, 'gap.over.perimeter.width')
        self.layersTo = config.getint(name, 'layers.to.index')
        self.edgeWidth = slicedModel.runtimeParameters.extrusionWidth
        brimWidth = config.getfloat(name, 'brim.width')
        self.skirtGap = self.gapOverPerimeterWidth * self.edgeWidth + brimWidth
        self.brimLoopsCount = int(brimWidth / self.edgeWidth)
        self.outerInner = config.getboolean(name, 'order.outer.inner')
        self.unifiedLoop = LoopCrossDictionary()
        self.createSegmentDictionaries(self.unifiedLoop)

    def skirt(self):
        'Add skirt to model'
        if self.layersTo > len(self.slicedModel.layers):
            self.layersTo = len(self.slicedModel.layers)

        self.addLayerToUnifiedLoop(self.slicedModel.layers[0])
        brimLoops = self.createSkirtLoops(0, self.brimLoopsCount)

        if self.gapOverPerimeterWidth != 0:

            for layerIndex in xrange(1, self.layersTo):
                self.addLayerToUnifiedLoop(self.slicedModel.layers[layerIndex])

            skirtLoops = self.createSkirtLoops(self.skirtGap, 1)

            for layerIndex in xrange(self.layersTo):
                for skirtLoop in skirtLoops:
                    supportPath = SupportPath(self.slicedModel.runtimeParameters)
                    supportPath.addPath(skirtLoop)
                    self.slicedModel.layers[layerIndex].supportPaths.append(supportPath)

        if self.outerInner:
            brimLoops.reverse()

        for brimLoop in brimLoops:
            supportPath = SupportPath(self.slicedModel.runtimeParameters)
            supportPath.addPath(brimLoop)
            self.slicedModel.layers[0].supportPaths.append(supportPath)

    def addLayerToUnifiedLoop(self, layer):
        'Adds layers outer outline and support path points to self.unifiedLoop'
        for outerRing in layer.nestedRings:
            loopCrossDictionary = LoopCrossDictionary()
            loopCrossDictionary.loop = outerRing.getXYBoundaries()
            self.createSegmentDictionaries(loopCrossDictionary)
            self.unifyLayer(loopCrossDictionary)

        for supportPath in layer.supportPaths:
            loopCrossDictionary = LoopCrossDictionary()
            loopCrossDictionary.loop = [supportPath.startPoint] + supportPath.points
            self.createSegmentDictionaries(loopCrossDictionary)
            self.unifyLayer(loopCrossDictionary)

    def createSegmentDictionaries(self, loopCrossDictionary):
        'Create horizontal and vertical segment dictionaries.'
        loopCrossDictionary.horizontalDictionary = self.getHorizontalXIntersectionsTable(loopCrossDictionary.loop)
        flippedLoop = euclidean.getDiagonalFlippedLoop(loopCrossDictionary.loop)
        loopCrossDictionary.verticalDictionary = self.getHorizontalXIntersectionsTable(flippedLoop)

    def getHorizontalXIntersectionsTable(self, loop):
        'Get the horizontal x intersections table from the loop.'
        horizontalXIntersectionsTable = {}
        euclidean.addXIntersectionsFromLoopForTable(loop, horizontalXIntersectionsTable, self.edgeWidth)
        return horizontalXIntersectionsTable

    def unifyLayer(self, loopCrossDictionary):
        'Union the loopCrossDictionary with the unifiedLoop.'
        euclidean.joinXIntersectionsTables(loopCrossDictionary.horizontalDictionary, self.unifiedLoop.horizontalDictionary)
        euclidean.joinXIntersectionsTables(loopCrossDictionary.verticalDictionary, self.unifiedLoop.verticalDictionary)

    def getOuterLoops(self, loops):
        'Get widdershins outer loops.'
        outerLoops = []
        for loop in loops:
            if not euclidean.isPathInsideLoops(outerLoops, loop):
                outerLoops.append(loop)
        intercircle.directLoops(True, outerLoops)
        return outerLoops

    def createSkirtLoops(self, gap, shellCount):
        'Create the skirt loops.'
        outset = gap + self.edgeWidth

        points = euclidean.getPointsByHorizontalDictionary(self.edgeWidth, self.unifiedLoop.horizontalDictionary)
        points += euclidean.getPointsByVerticalDictionary(self.edgeWidth, self.unifiedLoop.verticalDictionary)
        loops = triangle_mesh.getDescendingAreaOrientedLoops(points, points, 2.5 * self.edgeWidth)
        outerLoops = self.getOuterLoops(loops)

        skirtLoops = []
        for shellNo in xrange(shellCount):
            outsetLoops = intercircle.getInsetSeparateLoopsFromLoops(-(outset + self.edgeWidth * shellNo), outerLoops)
            outsetLoops = self.getOuterLoops(outsetLoops)
            if self.convex:
                outsetLoops = [euclidean.getLoopConvex(euclidean.getConcatenatedList(outsetLoops))]

            for outsetLoop in outsetLoops:
                skirtLoops.append(outsetLoop + [outsetLoop[0]])

        return skirtLoops

class LoopCrossDictionary:
    'Loop with a horizontal and vertical dictionary.'
    def __init__(self):
        'Initialize LoopCrossDictionary.'
        self.loop = []

    def __repr__(self):
        'Get the string representation of this LoopCrossDictionary.'
        return str(self.loop)
