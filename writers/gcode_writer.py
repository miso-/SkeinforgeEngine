from config import config
from fabmetheus_utilities.vector3 import Vector3
from entities import GcodeCommand, TravelPath
from plugins.comb import CombSkein
import StringIO
import gcodes
import sys
import time
import entities.paths as paths


class GcodeWriter:
    '''Writes the slicedFile for a sliced model.'''

    def __init__(self, slicedFile):
        self.slicedFile = slicedFile

    def getSlicedFile(self, verbose=False):
        '''Final Gcode representation.'''
        output = StringIO.StringIO()

        for startCommand in self.slicedFile.startGcodeCommands:
            output.write(printCommand(startCommand, verbose))

        self.slicedFile.printbed.rebuildGroupedLayers()
        for layerGroup in self.slicedFile.printbed.getLayersGroupedByZ():
            self.getLayerGroup(layerGroup, output, None, verbose)

        for endCommand in self.slicedFile.endGcodeCommands:
            output.write(printCommand(endCommand, verbose))

        return output.getvalue()

    def getLayerGroup(self, layerGroup, output, parentLookaheadStartVector=None, verbose=False):
        '''Final Gcode representation.'''

        for preLayerGcodeCommand in layerGroup[0][0].preLayerGcodeCommands:
            output.write(printCommand(preLayerGcodeCommand, verbose))

        pathList = []
        for (layer, volume, instance) in layerGroup:
            pathList += layer.getOrderedPathList()

        paths.resetExtrusionStats()

        pathListCount = len(pathList)

        for (index, path) in enumerate(pathList):
            if index + 1 < pathListCount:
                lookaheadStartPoint = pathList[index + 1].getStartPoint()
                lookaheadVector = Vector3(lookaheadStartPoint.real, lookaheadStartPoint.imag, layer.z)
            else:
                lookaheadVector = parentLookaheadStartVector

            previousVector = None
            if index > 0:
                previousPoint = pathList[index - 1].getEndPoint()
                previousVector = Vector3(previousPoint.real, previousPoint.imag, layer.z)

            nextPoint = path.getStartPoint()
            nextVector = Vector3(nextPoint.real, nextPoint.imag, layer.z)

            if self.slicedFile.runtimeParameters.combActive:
                combSkein = CombSkein(layer)
            else:
                combSkein = None

            travelPath = TravelPath(layer.runtimeParameters, previousVector, nextVector, combSkein)

            #TODO: We should have used sum of layer.z and containing nestedRing.z as pathheight here,
            #but this information is lost by getOrderedPathList method and nestedRing.z is allways
            #zero, so using plain layer.z is OK for now.
            self.getPath(travelPath, layer.z, output, None, layer.feedAndFlowRateMultiplier, verbose)

            self.getPath(path, layer.z, output, lookaheadVector, layer.feedAndFlowRateMultiplier, verbose)

        for postLayerGcodeCommand in layerGroup[0][0].postLayerGcodeCommands:
            output.write(printCommand(postLayerGcodeCommand, verbose))

    def getPath(self, path, pathHeight, output, lookaheadStartVector=None, feedAndFlowRateMultiplier=[1.0, 1.0], verbose=False):
        '''Final Gcode representation.'''
        pathExtruder = self.slicedFile.runtimeParameters.extruders[0]

        path.generateGcode(pathExtruder, pathHeight, lookaheadStartVector, feedAndFlowRateMultiplier, self.slicedFile.runtimeParameters)

        for command in path.gcodeCommands:
            output.write('%s' % printCommand(command, verbose))


def printCommand(command, verbose=False):

    if command is None:
        return
    if isinstance(command, GcodeCommand):
        return'%s\n' % command.str(verbose)
    else:
        return '%s\n' % command
