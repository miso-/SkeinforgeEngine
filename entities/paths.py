from GcodeCommand import GcodeCommand
from StringIO import StringIO
from config import config
from fabmetheus_utilities.vector3 import Vector3
from math import pi
from utilities import memory_tracker
import gcodes
import math
import sys
import time

# globals used as an easy way to maintain state between layer changes
_totalExtrusionDistance = 0.0
_previousPoint = None

def resetExtrusionStats():
    global _previousPoint    
    _previousPoint = None
    
class Path:
    ''' A Path the tool will follow within a nested ring.'''
    def __init__(self, runtimeParameters, z=0):
        
        self.z = z
        
        self.type = None
        self.startPoint = None
        self.points = []
        self.gcodeCommands = []
        
        self._setParameters(runtimeParameters)
        
    def _setParameters(self, runtimeParameters):
        self.decimalPlaces = runtimeParameters.decimalPlaces
        self.dimensionDecimalPlaces = runtimeParameters.dimensionDecimalPlaces
        self.speedActive = runtimeParameters.speedActive
        self.bridgeFeedRateMinute = runtimeParameters.bridgeFeedRateMinute
        self.perimeterFeedRateMinute = runtimeParameters.perimeterFeedRateMinute
        self.extrusionFeedRateMinute = runtimeParameters.extrusionFeedRateMinute
        self.travelFeedRateMinute = runtimeParameters.travelFeedRateMinute
        self.extrusionUnitsRelative = runtimeParameters.extrusionUnitsRelative
        self.supportFeedRateMinute = runtimeParameters.supportFeedRateMinute
        
        self.dimensionActive = runtimeParameters.dimensionActive
        
        self.zDistanceRatio = 5.0
        
        self.layerThickness = runtimeParameters.layerThickness
        self.perimeterWidth = runtimeParameters.perimeterWidth
        self.absolutePositioning = config.getboolean('preface', 'positioning.absolute')
        self.flowRate = runtimeParameters.flowRate
        self.perimeterFlowRate = runtimeParameters.perimeterFlowRate
        self.bridgeFlowRate = runtimeParameters.bridgeFlowRate
        self.combActive = runtimeParameters.combActive
                
        self.minimumBridgeFeedRateMultiplier = runtimeParameters.minimumBridgeFeedRateMultiplier
        self.minimumPerimeterFeedRateMultiplier = runtimeParameters.minimumPerimeterFeedRateMultiplier
        self.minimumExtrusionFeedRateMultiplier = runtimeParameters.minimumExtrusionFeedRateMultiplier
        self.minimumTravelFeedRateMultiplier = runtimeParameters.minimumTravelFeedRateMultiplier
        self.minimumLayerFeedRateMinute = runtimeParameters.minimumLayerFeedRateMinute
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO()
        output.write('%14stype: %s\n' % ('', self.type))
        output.write('%14sstartPoint: %s\n' % ('', self.startPoint))
        output.write('%14spoints: %s\n' % ('', self.points))
        output.write('%14sgcodeCommands:\n' % '')
        for command in self.gcodeCommands:
            output.write('%16s%s' % ('', GcodeCommand.printCommand(command)))
        return output.getvalue()    
    
    def getDistanceAndDuration(self):
        '''Returns the time taken to follow the path and the distance'''
        oldLocation = self.startPoint
        feedRate = self.getFeedRateMinute()
        feedRateSecond = feedRate / 60.0
        duration = 0.0
        distance = 0.0
        for point in self.points:
            
            separationX = point.real - oldLocation.real
            separationY = point.imag - oldLocation.imag
            segmentDistance = math.sqrt(separationX ** 2 + separationY ** 2)
            
            duration += segmentDistance / feedRateSecond
            distance += segmentDistance
            oldLocation = point
                
        return (distance, duration)
        
    def getStartPoint(self):
        return self.startPoint
    
    def getEndPoint(self):
        if len(self.points) > 0:
            return self.points[len(self.points) - 1]
        else:
            return None
        
    def getFeedRateMinute(self):
        '''Allows subclasses to override the relevant feedrate method so we don't have to use large if statements.'''
        return self.extrusionFeedRateMinute
    
    def getFlowRate(self):
        '''Allows subclasses to override the relevant flowrate method so we don't have to use large if statements.'''
        return self.flowRate

    def generateGcode(self, extruder, height, lookaheadStartVector=None, feedAndFlowRateMultiplier=[1.0, 1.0], runtimeParameters=None):
        'Transforms paths and points to gcode'
        global _previousPoint
        self.gcodeCommands = []
        
        if runtimeParameters != None:
            self._setParameters(runtimeParameters)
        
        if _previousPoint == None:
            _previousPoint = self.startPoint
        
        for point in self.points:
            
            gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                         ('Y', round(point.imag, self.decimalPlaces)),
                         ('Z', round(self.z + height, self.decimalPlaces))]
            
            pathFeedRateMinute = self.getFeedRateMinute()
            flowRate = self.getFlowRate()
            
            (pathFeedRateMinute, pathFeedRateMultiplier) = self.getFeedRateAndMultiplier(pathFeedRateMinute, feedAndFlowRateMultiplier[0])
            
            if self.speedActive:
                gcodeArgs.append(('F', pathFeedRateMinute))
                
            if self.dimensionActive:
                if self.absolutePositioning:
                        distance = abs(point - _previousPoint)
                        _previousPoint = point
                                                                
                extrusionDistance = extruder.getExtrusionDistance(distance, flowRate * feedAndFlowRateMultiplier[1], pathFeedRateMinute)
                gcodeArgs.append(('%s' % extruder.axisCode, '%s' % extrusionDistance))
                
            self.gcodeCommands.append(
                GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
        
    def getFeedRateAndMultiplier(self, feedRateMinute, feedRateMultiplier):
        'Returns the multiplier that results in either the minimum feed rate or the slowed down feed rate'
        if (feedRateMultiplier * feedRateMinute) < self.minimumLayerFeedRateMinute:
            return (self.minimumLayerFeedRateMinute, self.minimumLayerFeedRateMinute / feedRateMinute)
        else:
            return (feedRateMinute * feedRateMultiplier, feedRateMultiplier)
        

    def offset(self, offset):
        if self.startPoint != None:
            self.startPoint = complex(self.startPoint.real + offset.real, self.startPoint.imag + offset.imag)
        for (index, point) in enumerate(self.points):
            self.points[index] = complex(point.real + offset.real, point.imag + offset.imag)

    def addPath(self, path):
        'Add a path to the output.'
        if len(path) > 0:        
            self.startPoint = path[0]
            self.points = path[1 :]
        else:
            logger.warning('Zero length vertex positions array which was skipped over, this should never happen.')
        if len(path) < 2:
            logger.warning('Path of only one point: %s, this should never happen.', path)

class Loop(Path):
    def __init__(self, runtimeParameters, z=0):
        Path.__init__(self, runtimeParameters, z)

class InfillPath(Path):
    def __init__(self, runtimeParameters, z=0):        
        Path.__init__(self, runtimeParameters, z)
            
class SupportPath(Path):
    def __init__(self, runtimeParameters, z=0):        
        Path.__init__(self, runtimeParameters, z)

    def getFeedRateMinute(self):
        return self.supportFeedRateMinute
    
class TravelPath(Path):
    '''Moves from one path to another without extruding. Optionally dodges gaps (comb) and retracts (dimension)'''
    
    def __init__(self, runtimeParameters, fromLocation, toLocation, combSkein, z=0):
        Path.__init__(self, runtimeParameters, z)
        self.fromLocation = fromLocation
        self.toLocation = toLocation
        self.combSkein = combSkein
        
        if fromLocation != None:
            self.startPoint = fromLocation.dropAxis()
        else:  
            self.startPoint = toLocation.dropAxis()
            
        self.points.append(toLocation.dropAxis())
        
    def offset(self, offset):
        self.fromLocation.x += offset.real
        self.fromLocation.y += offset.imag            
        self.toLocation.x += offset.real
        self.toLocation.y += offset.imag            
        Path.offset(self, offset)
        
    def __str__(self):
        output = StringIO()
        output.write('\n%12sfromLocation: %s\n' % ('', self.fromLocation))
        output.write('%12stoLocation: %s\n' % ('', self.toLocation))
        output.write(Path.__str__(self))
        return output.getvalue()

    def moveToStartPoint(self, height, feedAndFlowRateMultiplier):
        '''Adds gcode to move the nozzle to the startpoint of the path. 
            If comb is active the path will dodge all open spaces.
        '''
        startPointPath = []
        global _previousPoint
        
        if self.combActive and self.fromLocation != None and self.combSkein != None: 
            
            additionalCommands = self.combSkein.getPathsBetween(self.z + height, self.fromLocation.dropAxis(), self.toLocation.dropAxis())
            startPointPath.extend(additionalCommands)
        
        startPointPath.append(self.toLocation.dropAxis())
        
        for point in startPointPath:
            gcodeArgs = [('X', round(point.real, self.decimalPlaces)),
                ('Y', round(point.imag, self.decimalPlaces)),
                ('Z', round(self.z + height, self.decimalPlaces))]
            
            if self.speedActive:
                travelFeedRateMinute, travelFeedRateMultiplier = self.getFeedRateAndMultiplier(self.travelFeedRateMinute, feedAndFlowRateMultiplier)
                gcodeArgs.append(('F', self.travelFeedRateMinute * travelFeedRateMultiplier))
            
            if self.absolutePositioning:
                _previousPoint = point
            else:
                _previousPoint += point            
                
            self.gcodeCommands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, gcodeArgs))
                        
    def generateGcode(self, pathExtruder, height, lookaheadStartVector=None, feedAndFlowRateMultiplier=[1.0, 1.0], runtimeParameters=None):
        'Transforms paths and points to gcode'
        global _previousPoint
        
        if runtimeParameters != None:
            self._setParameters(runtimeParameters)
            
        if _previousPoint == None:
            _previousPoint = self.startPoint
        
        if self.dimensionActive:
            
            if self.fromLocation != None:
                
                locationMinusOld = self.toLocation - self.fromLocation
                xyTravel = abs(locationMinusOld.dropAxis())
                zTravelMultiplied = locationMinusOld.z * self.zDistanceRatio
                timeToNextThread = math.sqrt(xyTravel * xyTravel + zTravelMultiplied * zTravelMultiplied) / self.extrusionFeedRateMinute * 60
            else:
                timeToNextThread = 0.0
            
            self.gcodeCommands.extend(pathExtruder.getRetractCommands(timeToNextThread, self.getFeedRateMinute()))
            
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_OFF))
        
        self.moveToStartPoint(height, feedAndFlowRateMultiplier[0])
    
        if self.dimensionActive:
            #_previousPoint = self.startPoint            
            self.gcodeCommands.extend(pathExtruder.getRetractReverseCommands())
            
        self.gcodeCommands.append(GcodeCommand(gcodes.TURN_EXTRUDER_ON))        
               
    
    def getFeedRateMinute(self):
        return self.travelFeedRateMinute
    
class BoundaryPerimeter(Path):
    
    def __init__(self, runtimeParameters, z=0):
        Path.__init__(self, runtimeParameters, z)
        self.boundaryPoints = []

    def __str__(self):
        output = StringIO()
        output.write('%12sboundaryPerimeter:\n' % '')
        output.write('%14sboundaryPoints: %s\n' % ('', self.boundaryPoints))
        output.write(Path.__str__(self))
        return output.getvalue()
    
    def offset(self, offset):
        for boundaryPoint in self.boundaryPoints:
            boundaryPoint.x += offset.real
            boundaryPoint.y += offset.imag            
        Path.offset(self, offset)
        
    def getFeedRateMinute(self):
        return self.perimeterFeedRateMinute
    
    def getFlowRate(self):
        return self.perimeterFlowRate