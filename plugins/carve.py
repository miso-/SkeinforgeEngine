"""
Carve is a script to carve a shape into svg slice layers. It creates the perimeter contours

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from fabmetheus_utilities import archive, svg_writer, vector3
from entities import Placement
from importlib import import_module
import logging
import os
import sys
import math

name = 'carve'
logger = logging.getLogger(name)

__interpret_plugins_path__ = 'fabmetheus_utilities/fabmetheus_tools/interpret_plugins'


def performAction(slicedFile):
    "Get carved text."
    fileExtension = os.path.splitext(slicedFile.fileName)[1][1:].lower()
    sys.path.insert(0, __interpret_plugins_path__)
    pluginModule = import_module(fileExtension)
    if pluginModule is None:
        return None
    pluginModule.getCarving(slicedFile)

    slicedFile.getObjectListToSlice()
    preparePrintbed(slicedFile)

    if config.getboolean(name, 'debug'):
        for object in slicedFile.getObjectListToSlice():
            for (vIndex, volume) in enumerate(object.volumes):
                carvingFilename = slicedFile.fileName[: slicedFile.fileName.rfind('.')] + '_obj' + str(object.objectId) + '-vol' + str(vIndex) + '.carving.xml'
                archive.writeFileText(carvingFilename, str(volume.triangleMesh))
                logger.info("Carving XML written to %s", carvingFilename)
    CarveSkein(slicedFile).carve()


def preparePrintbed(slicedFile):

    derivedObjects = []

    for instance in slicedFile.printbed.instances:
        object = instance.object
        placement = instance.placement
        shiftZ = placement.displacement.z

        if placement.rotatesOutOfXYPlane() or shiftZ % slicedFile.runtimeParameters.layerHeight != 0:

            success = False
            for derObj in derivedObjects:
                if object == derObj.derivedFrom.object:
                    placementDiff = placement / derObj.derivedFrom.placement
                    if not placementDiff.rotatesOutOfXYPlane() and not placementDiff.displacement.z % slicedFile.runtimeParameters.layerHeight:
                        instance.object = derObj
                        instance.placement = placementDiff
                        success = True
                        break

            if not success:
                derivedObject = instance.object.getDerivedObject(instance.placement)
                instance.object = derivedObject
                instance.placement = Placement()
                derivedObjects.append(derivedObject)


class CarveSkein:
    "A class to carve a 3D model."

    def __init__(self, slicedFile):
        'Initialize'
        self.slicedFile = slicedFile
        self.layerHeight = config.getfloat(name, 'layer.height')
        self.extrusionWidth = config.getfloat(name, 'extrusion.width')
        self.infillBridgeDirection = config.getboolean(name, 'infill.bridge.direction')
        self.importCoarsenessRatio = config.getfloat(name, 'import.coarseness.ratio')
        self.correctMesh = config.getboolean(name, 'mesh.correct')
        self.decimalPlaces = config.getint('general', 'decimal.places')
        self.layerPrintFrom = config.getint(name, 'layer.print.from')
        self.layerPrintTo = config.getint(name, 'layer.print.to')

    def carve(self):

        for object in self.slicedFile.getObjectListToSlice():
            for volume in object.volumes:
                self.carveVolume(volume)

    def carveVolume(self, volume):
        "Parse 3D model file and store the carved slicedFile."

        carving = volume.triangleMesh
        carving.setCarveInfillInDirectionOfBridge(self.infillBridgeDirection)
        carving.setCarveLayerThickness(self.layerHeight)
        importRadius = 0.5 * self.importCoarsenessRatio * abs(self.extrusionWidth)
        carving.setCarveImportRadius(max(importRadius, 0.001 * self.layerHeight))
        carving.setCarveIsCorrectMesh(self.correctMesh)

        rotatedLoopLayers = carving.getCarveRotatedBoundaryLayers()

        if len(rotatedLoopLayers) < 1:
            logger.warning('There are no slices for the model, this could be because the model is too small for the Layer Thickness.')
            return

        volume.carvingCornerMaximum = carving.getCarveCornerMaximum()
        volume.carvingCornerMinimum = carving.getCarveCornerMinimum()

        toBePrintedLayers = rotatedLoopLayers[self.layerPrintFrom: self.layerPrintTo]
        for toBePrintedLayer in toBePrintedLayers:
            sortedLoops = []
            for toBePrintedLayerLoop in toBePrintedLayer.loops:
                lowerLeftPoint = self.getLowerLeftCorner(toBePrintedLayerLoop)
                lowerLeftIndex = toBePrintedLayerLoop.index(lowerLeftPoint)
                sortedLoops.append(toBePrintedLayerLoop[lowerLeftIndex:] + toBePrintedLayerLoop[:lowerLeftIndex])
            toBePrintedLayer.loops = sortedLoops

        volume.rotatedLoopLayers = toBePrintedLayers

        if config.getboolean(name, 'debug'):
            filename = self.slicedFile.fileName
            svgFilename = filename[: filename.rfind('.')] + '_obj' + str(volume.parentObject.objectId) + '-vol' + str(volume.parentObject.volumes.index(volume)) + '.svg'
            svgWriter = svg_writer.SVGWriter(True,
                                             volume.carvingCornerMaximum,
                                             volume.carvingCornerMinimum,
                                             self.slicedFile.runtimeParameters.decimalPlaces,
                                             self.slicedFile.runtimeParameters.layerHeight,
                                             self.slicedFile.runtimeParameters.layerThickness)
            archive.writeFileText(svgFilename, svgWriter.getReplacedSVGTemplate(svgFilename[: svgFilename.rfind('.')], '', volume.rotatedLoopLayers))
            logger.info("Carving SVG written to %s", svgFilename)

    def getLowerLeftCorner(self, points):
        'Get the lower left corner point from a set of points.'
        lowerLeftCorner = None
        lowestRealPlusImaginary = 987654321.0
        for point in points:
            realPlusImaginary = point.real + point.imag
            if realPlusImaginary < lowestRealPlusImaginary:
                lowestRealPlusImaginary = realPlusImaginary
                lowerLeftCorner = point
        return lowerLeftCorner
