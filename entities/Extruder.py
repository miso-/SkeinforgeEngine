from GcodeCommand import GcodeCommand
from config import config
from math import pi
import gcodes


def setupExtruders(slicedFile):

    slicedFile.runtimeParameters.extruders = []

    extruderSections = []

    for section in config.sections():
        if section.startswith('Extruder'):
            slicedFile.runtimeParameters.extruders.append(Extruder(slicedFile.runtimeParameters, section))


class Extruder:

    def __init__(self, runtimeParameters, section):
        self.extrussionDistance = 0
        self.lastRetractDistance = 0
        self.filamentExtruded = 0

        self._setParameters(runtimeParameters, section)

    def _setParameters(self, runtimeParameters, section):
        self.decimalPlaces = runtimeParameters.decimalPlaces
        self.dimensionDecimalPlaces = runtimeParameters.dimensionDecimalPlaces
        self.extrusionUnitsRelative = runtimeParameters.extrusionUnitsRelative

        self.layerThickness = runtimeParameters.layerThickness
        self.perimeterWidth = runtimeParameters.perimeterWidth
        self.travelFeedRateMinute = runtimeParameters.travelFeedRateMinute

        self.name = config.get(section, 'name')
        self.filamentDiameter = config.getfloat(section, 'filament.diameter')
        self.filamentPackingDensity = config.getfloat(section, 'filament.packing.density')
        self.oozeRate = config.getfloat(section, 'oozerate')
        self.extruderRetractionSpeedMinute = round(60.0 * config.getfloat(section, 'retraction.speed'), self.dimensionDecimalPlaces)
        self.maximumRetractionDistance = config.getfloat(section, 'maximum.retraction')
        self.axisCode = config.get(section, 'axis.code')

        filamentRadius = 0.5 * self.filamentDiameter
        filamentPackingArea = pi * filamentRadius * filamentRadius * self.filamentPackingDensity
        extrusionArea = pi * self.layerThickness ** 2 / 4 + self.layerThickness * (self.perimeterWidth - self.layerThickness)
            #http://hydraraptor.blogspot.sk/2011/03/spot-on-flow-rate.html
        self.flowScaleSixty = 60.0 * extrusionArea / filamentPackingArea

    def getExtrusionDistance(self, distance, flowRate, feedRateMinute):

        scaledFlowRate = flowRate * self.flowScaleSixty
        extrusionDistance = scaledFlowRate / feedRateMinute * distance

        self.filamentExtruded += extrusionDistance

        if self.extrusionUnitsRelative:
            extrusionDistance = round(extrusionDistance, self.dimensionDecimalPlaces)
        else:
            self.extrussionDistance += extrusionDistance
            extrusionDistance = round(self.extrussionDistance, self.dimensionDecimalPlaces)

        return extrusionDistance

    def getRetractCommands(self, idleTime, resumingSpeed):

        commands = []

        retractDistance = min(idleTime * abs(self.oozeRate) / 60, self.maximumRetractionDistance)
        self.lastRetractDistance = retractDistance

        if self.extrusionUnitsRelative:
            retractDistance = round(-retractDistance, self.dimensionDecimalPlaces)
        else:
            self.extrusionDistance -= retractDistance
            retractDistance = round(self.extrusionDistance, self.dimensionDecimalPlaces)

        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('%s' % self.axisCode, '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % resumingSpeed)]))

        return commands

    def getRetractReverseCommands(self):

        commands = []

        if self.extrusionUnitsRelative:
            retractDistance = round(self.lastRetractDistance, self.dimensionDecimalPlaces)
        else:
            self.extrusionDistance += self.lastRetractDistance
            retractDistance = round(self.extrusionDistance, self.dimensionDecimalPlaces)

        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.extruderRetractionSpeedMinute)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('%s' % self.axisCode, '%s' % retractDistance)]))
        commands.append(GcodeCommand(gcodes.LINEAR_GCODE_MOVEMENT, [('F', '%s' % self.travelFeedRateMinute)]))

        if not self.extrusionUnitsRelative:
            commands.append(self.getResetExtruderDistanceCommand())

        return commands

    def getResetExtruderDistanceCommand(self):

        self.extrusionDistance = 0.0
        return GcodeCommand(gcodes.RESET_EXTRUDER_DISTANCE, [('E', '0')])
