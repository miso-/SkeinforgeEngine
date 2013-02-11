from StringIO import StringIO
from config import config
from entities import NestedRing, GcodeCommand
from Placement import Placement
from fabmetheus_utilities.vector3 import Vector3
from utilities import memory_tracker
import logging
import gcodes
import sys
import time

name = 'Layer'
logger = logging.getLogger(name)


class Layer:
    def __init__(self, z, index, runtimeParameters):
        self.z = z
        self.index = index
        self.runtimeParameters = runtimeParameters
        self.bridgeRotation = None
        self.nestedRings = []
        self.preLayerGcodeCommands = []
        self.postLayerGcodeCommands = []
        self.feedAndFlowRateMultiplier = [1.0, 1.0]

        self.preSupportGcodeCommands = []
        self.postSupportGcodeCommands = []
        self.supportPaths = []

        if runtimeParameters.profileMemory:
            memory_tracker.track_object(self)

        if self.runtimeParameters.dimensionActive:
            if self.runtimeParameters.extrusionUnitsRelative:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.RELATIVE_EXTRUSION_DISTANCE))
            else:
                self.preLayerGcodeCommands.append(GcodeCommand(gcodes.ABSOLUTE_EXTRUSION_DISTANCE))

        self.combSkein = None

    def __str__(self):
        '''Get the string representation.'''
        output = StringIO()

        output.write('%2slayer (%s) z:%s\n' % ('', self.index, self.z))

        output.write('%2slayer feedAndFlowRateMultiplier:%s\n' % ('', self.feedAndFlowRateMultiplier))

        if self.bridgeRotation is not None:
            output.write('bridgeRotation: %s \n' % self.bridgeRotation)

        output.write('%4spreLayerGcodeCommand:\n' % (''))
        for preLayerGcodeCommand in self.preLayerGcodeCommands:
            output.write('%4s %s' % ('', GcodeCommand.printCommand(preLayerGcodeCommand, self.runtimeParameters.verboseGcode)))

        output.write('%4spreSupportGcodeCommands:\n' % (''))
        for preSupportGcodeCommand in self.preSupportGcodeCommands:
            output.write('%4s %s' % ('', GcodeCommand.printCommand(preSupportGcodeCommand, self.runtimeParameters.verboseGcode)))

        output.write('%4ssupportLayerPaths:\n' % '')
        for supportPath in self.supportPaths:
            output.write(supportPath)

        output.write('%4spostSupportGcodeCommands:\n' % (''))
        for postSupportGcodeCommand in self.postSupportGcodeCommands:
            output.write('%4s %s' % ('', GcodeCommand.printCommand(postSupportGcodeCommand, self.runtimeParameters.verboseGcode)))

        output.write('%4snestedRings:' % (''))
        for nestedRing in self.nestedRings:
            output.write(nestedRing)

        output.write('\n%4spostLayerGcodeCommand:' % (''))
        for postLayerGcodeCommand in self.postLayerGcodeCommands:
            output.write('%4s %s' % ('', GcodeCommand.printCommand(postLayerGcodeCommand, self.runtimeParameters.verboseGcode)))

        return output.getvalue()

    def getDistanceAndDuration(self):
        '''Returns the amount of time needed to print the layer, and the distance to travel. Note, this currently ignores commands in the pre and post layer list.'''
        duration = 0.0
        distance = 0.0

        for nestedRing in self.nestedRings:
            (nestedRingDistance, nestedRingDuration) = nestedRing.getDistanceAndDuration()
            distance += nestedRingDistance
            duration += nestedRingDuration

        for supportPath in self.supportPaths:
            (supportPathDistance, supportPathDuration) = supportPath.getDistanceAndDuration()
            distance += supportPathDistance
            duration += supportPathDuration

        return (distance, duration)

    def getOrderedPathList(self):
        pathList = []

        self.getSupportPaths(pathList)

        threadFunctionDictionary = {
            'infill': self.getInfillPaths, 'loops': self.getLoopPaths, 'perimeter': self.getPerimeterPaths}
        for threadType in self.runtimeParameters.extrusionPrintOrder:
            threadFunctionDictionary[threadType](pathList)

        return pathList

    def getSupportPaths(self, pathList):
        for supportPath in self.supportPaths:
            pathList.append(supportPath)

    def getPerimeterPaths(self, pathList):
        for nestedRing in self.nestedRings:
            nestedRing.getPerimeterPaths(pathList)

    def getLoopPaths(self, pathList):
        for nestedRing in self.nestedRings:
            nestedRing.getLoopPaths(pathList)

    def getInfillPaths(self, pathList):
        for nestedRing in self.nestedRings:
            nestedRing.getInfillPaths(pathList)

    def getStartPoint(self):
        if len(self.nestedRings) > 0:
            return self.nestedRings[0].getStartPoint()

    def getPlaced(self, placement):
        '''Returns copy of Layer spatially trasnformed by placement'''

        if placement.rotatesOutOfXYPlane():
            logger.error('Can\'t rotate Layer out of XY plane! rot = %s' % placement.getRotation())
            return None

        result = Layer(self.z + placement.displacement.z, self.index, self.runtimeParameters)

        vec = Vector3(placement.displacement.x, placement.displacement.y, 0)
        newPlacement = Placement(vec, placement.getRotation())

        result.bridgeRotation = self.bridgeRotation  # ?

        for nestedRing in self.nestedRings:
            result.nestedRings.append(nestedRing.getPlaced(newPlacement))

        result.preLayerGcodeCommands = self.preLayerGcodeCommands
        result.postLayerGcodeCommands = self.postLayerGcodeCommands
        result.feedAndFlowRateMultiplier = self.feedAndFlowRateMultiplier

        result.preSupportGcodeCommands = self.preSupportGcodeCommands
        result.postSupportGcodeCommands = self.postSupportGcodeCommands
        result.supportPaths = []

        return result

    def addNestedRing(self, nestedRing):
        self.nestedRings.append(nestedRing)

    def isBridgeLayer(self):
        return self.bridgeRotation is not None
