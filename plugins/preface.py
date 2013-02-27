"""
Preface creates the nested ring structure from the rotated layers, and adds optional start and end gcodes.

Credits:
        Original Author: Enrique Perez (http://skeinforge.com)
        Contributors: Please see the documentation in Skeinforge
        Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)

License:
        GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from entities import NestedRing, GcodeCommand, Layer, BoundaryPerimeter
from fabmetheus_utilities import euclidean, archive
from time import strftime
import gcodes
import logging
import os

name = __name__
logger = logging.getLogger(name)


def performAction(slicedFile):
    "Preface and converts the layers."
    PrefaceSkein(slicedFile).preface()


class PrefaceSkein:
    "A class to preface a skein of extrusions."

    def __init__(self, slicedFile):
        self.slicedFile = slicedFile
        self.setPositioningToAbsolute = config.getboolean(name, 'positioning.absolute')
        self.setUnitsToMillimeters = config.getboolean(name, 'units.millimeters')
        self.startAtHome = config.getboolean(name, 'startup.at.home')
        self.resetExtruder = config.getboolean(name, 'startup.extruder.reset')
        self.endFile = config.get(name, 'end.file')
        self.startFile = config.get(name, 'start.file')
        self.layerHeight = self.slicedFile.runtimeParameters.layerHeight

    def preface(self):
        "Prefaces and converts the svg text to Gcode."

        self.addStartCommandsToGcode()

        for object in self.slicedFile.getObjectListToSlice():
            self.prefaceObject(object)

        self.addEndCommandsToGcode()

    def prefaceObject(self, object):

        for volume in object.volumes:
            for (index, rotatedLoopLayer) in enumerate(volume.rotatedLoopLayers):
                self.addPrefaceToGcode(index, rotatedLoopLayer, volume)

    def addPrefaceToGcode(self, index, rotatedLoopLayer, volume):
        decimalPlaces = self.slicedFile.runtimeParameters.decimalPlaces

        # adding 0.5*layerHeight is needed to get layer[0].z == layerHeight
        z = round(rotatedLoopLayer.z + (self.layerHeight * 0.5), 3)
        layer = Layer(z, index, self.slicedFile.runtimeParameters)

        if rotatedLoopLayer.rotation != None:
            layer.bridgeRotation = complex(rotatedLoopLayer.rotation)

        loops = rotatedLoopLayer.loops
        internalLoops = self.createLoopHierarchy(loops)

        nestRingPlaceholder = {}
        for loop in loops:
            nestedRing = NestedRing(self.slicedFile.runtimeParameters)
            nestedRing.setBoundaryPerimeter(loop)
            nestRingPlaceholder[str(loop)] = nestedRing

        for internalLoop in internalLoops:
            parent = internalLoops[internalLoop]
            child = loops[internalLoop]
            childNestedRing = nestRingPlaceholder[str(loops[internalLoop])]

            if parent == None:
                layer.addNestedRing(childNestedRing)
            else:
                parentNestedRing = nestRingPlaceholder[str(internalLoops[internalLoop])]
                parentNestedRing.innerNestedRings.append(childNestedRing)

        volume.layers.append(layer)

    def createLoopHierarchy(self, loops):
        internalLoops = {}

        for (loopIndex, loop) in enumerate(loops):
            internalLoops[loopIndex] = []
            otherLoops = []
            for beforeIndex in xrange(loopIndex):
                otherLoops.append(loops[beforeIndex])
            for afterIndex in xrange(loopIndex + 1, len(loops)):
                otherLoops.append(loops[afterIndex])
            internalLoops[loopIndex] = euclidean.getClosestEnclosingLoop(otherLoops, loop)
        return internalLoops

    def addStartCommandsToGcode(self):
        if config.get(name, 'start.file') != None:
            for line in archive.getLinesFromAlterationsFile(self.startFile):
                self.slicedFile.startGcodeCommands.append(line)

        if self.setPositioningToAbsolute:
            self.slicedFile.startGcodeCommands.append(GcodeCommand(gcodes.ABSOLUTE_POSITIONING))
        if self.setUnitsToMillimeters:
            self.slicedFile.startGcodeCommands.append(GcodeCommand(gcodes.UNITS_IN_MILLIMETERS))
        if self.startAtHome:
            self.slicedFile.startGcodeCommands.append(GcodeCommand(gcodes.START_AT_HOME))
        if self.resetExtruder:
            self.slicedFile.startGcodeCommands.append(GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')]))

    def addEndCommandsToGcode(self):
        if config.get(name, 'end.file') != None:
            for line in archive.getLinesFromAlterationsFile(self.endFile):
                self.slicedFile.endGcodeCommands.append(line)
