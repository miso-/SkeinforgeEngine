from fabmetheus_utilities.vector3 import Vector3
from Instance import Instance
from Placement import Placement
import logging

name = 'Constellation'
logger = logging.getLogger(name)


class Constellation:

    def __init__(self, objectId=None, instances=None):

        self.objectId = objectId
        self.instances = []
        self.layersGroupedByZ = []

        if instances is not None:
            self.addInstances(instances)

    def __str__(self):

        instances = ''
        for instance in self.instances:
            instances += '\n'
            for line in str(instance).splitlines():
                instances += '\n\t' + line

        return 'Constellation ID: {0}{1}'.format(self.objectId, instances)

    def addInstances(self, instances):
        '''Adds instances into constellation'''

        self.instances += instances

    def getInstances(self, recursive=False, currentPlacement=Placement(), topologyPath=None):
        '''Returns list of all instances contained in constellation.'''

        if topologyPath is None:
            topologyPath = []

        topologyPath.append(self.objectId)

        result = []
        for instance in self.instances:
            if hasattr(instance.object, 'getInstances'):
                if instance.object.objectId in topologyPath:
                    logger.warning('Loop in constellation topology! Topology path: {0} -> {1}'.format(topologyPath, instance.object.objectId))
                elif recursive:
                    result += instance.object.getInstances(True, currentPlacement * instance.placement, topologyPath)
            else:
                inst = Instance(instance.object, currentPlacement * instance.placement)
                result.append(inst)

        topologyPath.pop()
        return result

    def getObjects(self, recursive=False, topologyPath=None):
        '''Returns list of all objects contained in constellation.'''

        if topologyPath is None:
            topologyPath = []

        topologyPath.append(self.objectId)

        result = []
        for instance in self.instances:
            if hasattr(instance.object, 'getInstances'):
                if instance.object.objectId in topologyPath:
                    logger.warning('Loop in constellation topology! Topology path: {0} -> {1}'.format(topologyPath, instance.object.objectId))
                elif recursive:
                    result += instance.object.getObjects(True)
            elif instance.object not in result:
                result.append(instance.object)

        topologyPath.pop()
        return result

    def getLayersGroupedByZ(self):
        '''Retruns list of layerGroups groupped by layer height.'''
        if len(self.layersGroupedByZ) == 0:
            self.rebuildGroupedLayers()

        return self.layersGroupedByZ

    def rebuildGroupedLayers(self):
        '''(Re)builds layersGroupedByZ list returned by getLayersGroupedByZ method.'''

        instances = self.instances
        layerIndexes = [0] * len(instances)
        self.layersGroupedByZ = []

        for (instanceIndex, layerIndex) in enumerate(layerIndexes):
            if len(instances[instanceIndex].object.getLayersGroupedByZ()) == 0:
                layerIndexes[instanceIndex] = None

        while len([layerIndex for layerIndex in layerIndexes if layerIndex is not None]) > 0:

            nextZ = min([instances[instanceIndex].object.getLayersGroupedByZ()[layerIndex][0][0].z for instanceIndex, layerIndex in enumerate(layerIndexes) if layerIndex is not None])

            layerGroup = []
            for instanceIndex, layerIndex in enumerate(layerIndexes):
                if layerIndex is None:
                    continue
                instance = instances[instanceIndex]
                z = instances[instanceIndex].object.getLayersGroupedByZ()[layerIndex][0][0].z

                if z == nextZ:
                    for (layer, volume) in instances[instanceIndex].object.getLayersGroupedByZ()[layerIndex]:
                        layerGroup.append((layer, volume, instance))
                    if len(instance.object.getLayersGroupedByZ()) > layerIndex + 1:
                        layerIndexes[instanceIndex] += 1
                    else:
                        layerIndexes[instanceIndex] = None

            self.layersGroupedByZ.append(layerGroup)

    def finalize(self):
        '''Puts all objects contained in constellation into their final positions.'''

        for instance in self.instances:
            placement = instance.placement
            object = instance.object
            instance.object = object.getDerivedObject(placement)
            instance.placement = Placement()
