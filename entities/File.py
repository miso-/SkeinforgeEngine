from RuntimeParameters import RuntimeParameters
from GcodeCommand import GcodeCommand
from Constellation import Constellation
from Instance import Instance
import logging

name = 'File'
logger = logging.getLogger(name)


class File:

    def __init__(self, fileName):

        self.fileName = fileName
        self.objectIds = {}
        self.materialIds = {}
        self.textureIds = {}
        self.metadata = None

        self.objects = []
        self.constellations = []

        self.startGcodeCommands = []
        self.endGcodeCommands = []
        self.runtimeParameters = RuntimeParameters()

        self.printbed = Constellation(-1)

    def getObjectListToSlice(self):
        '''Returns the list of objects to slice'''

        return self.printbed.getObjects()

    def getTopLevelConstellations(self):
        '''Returns top level constellations'''

        topLevelConstellations = list(self.constellations)

        for constellation in self.constellations:
            for instance in constellation.instances:
                if instance.object in topLevelConstellations:
                    topLevelConstellations.remove(instance.object)

        return topLevelConstellations

    def addObjectIds(self, objectIds):

        for objectId in objectIds:
            self.objectIds = dict(objectIds, **self.objectIds)

    def addObjects(self, objects):

        for object in objects:
            if object.objectId in self.objectIds.keys():
                logger.warning("Ignoring duplicate objectId: %d", object.objectId)
                continue
            object.slicedFile = self
            self.objectIds[int(object.objectId)] = object
            self.objects.append(object)

    def addConstellations(self, constellations):

        for constellation in constellations:
            if constellation.objectId in self.objectIds.keys():
                logger.warning("Ignoring duplicate objectId: %d", constellation.objectId)
                continue
            self.objectIds[int(constellation.objectId)] = constellation
            self.constellations.append(constellation)

    def addTextures(self, textures):

        for texture in textures:
            if texture.id in self.textureIds.keys():
                logger.warning("Ignoring duplicate textureId: %d", texture.id)
                continue
            self.textureIds[int(texture.id)] = texture

    def addMaterials(self, materials):

        for material in materials:
            if material.id in self.materialIds.keys():
                logger.warning("Ignoring duplicate materialId: %d", material.id)
                continue
            self.materialIds[int(material.id)] = material

    def setMetadata(self, metadata):

        self.metadata = metadata
