from config import config
from StringIO import StringIO
import gcodes
import math
import sys
import time
from RuntimeParameters import RuntimeParameters
from GcodeCommand import GcodeCommand 

class SlicedModel:
    '''Runtime data for conversion of 3D model to gcode.'''
    
    def __init__(self):

        self.runtimeParameters = RuntimeParameters()
        self.layers = []
        
        self.startGcodeCommands = []
        self.endGcodeCommands = []
        self.elementOffsets = None

        self.svgText = None
        self.carvingCornerMaximum = None
        self.carvingCornerMinimum = None
        
        # Can we remove this after reading the carving once the layers have been generated??
        self.rotatedLoopLayers = []
        
    def __str__(self):
        '''Get the string representation.'''
        output = StringIO()
        
        output.write("\nRuntimeParameters:\n%s\n" % vars(self.runtimeParameters))
        
        output.write("\nelementOffsets: %s\n" % self.elementOffsets)
        
        output.write("\nrotatedLoopLayers:\n")
        for rotatedLoopLayer in self.rotatedLoopLayers:
            output.write('%s\n' % vars(rotatedLoopLayer))
            
        output.write("\nstartGcodeCommands:\n")
        for startGcodeCommand in self.startGcodeCommands:
            output.write(GcodeCommand.printCommand(startGcodeCommand, self.runtimeParameters.verboseGcode))
        
        output.write("\nlayers:\n")
        for layer in self.layers:
            output.write('%s\n' % layer)
       
        output.write("\nendGcodeCommands:\n")
        for endGcodeCommand in self.endGcodeCommands:
            output.write(GcodeCommand.printCommand(endGcodeCommand, self.runtimeParameters.verboseGcode))
             
        return output.getvalue()
        
    def insertLayers(self, layers, index):
        '''Inserts list of layers at position given by index.'''

        insertedHeigth = layers[-1].z

        self.shiftLayers(insertedHeigth, index)
        self.layers = self.layers[:index] + layers + self.layers[index:]

        for i in xrange(index, len(self.layers)):
            self.layers[i].index = i

    def shiftLayers(self, shiftHeigth, startIndex=0, stopIndex=None):
        '''Shifts interval of layers by amount specified in shiftHeigth. Use with care to not cause overlaps!'''

        if stopIndex == None:
            stopIndex = len(self.layers)

        for i in xrange(startIndex, stopIndex):
            self.layers[i].z += shiftHeigth
