from Volume import Volume
from Instance import Instance
from Placement import Placement
import copy


class Object:

    def __init__(self, objectId, meshVertices, volumes, color=None, metadata=None, derivedFrom=None):

        self.slicedFile = None
        self.objectId = int(objectId)
        self.color = color
        self.metadata = metadata
        self.derivedFrom = derivedFrom

        self.meshVertices = meshVertices
        self.volumes = []

        self.carvingCornerMaximum = None
        self.carvingCornerMinimum = None
        self.layersGroupedByZ = []

        for volume in volumes:
            self.addVolume(volume)

    def __str__(self):

        return 'Object ID: %s' % self.objectId

    def addVolume(self, volume):

        volume.parentObject = self
        volume.triangleMesh.vertexes = self.meshVertices

        self.volumes.append(volume)

    def getDerivedObject(self, placement, objectId=None):

        if placement == Placement():
            return self

        if objectId is None:
            objectId = max(self.slicedFile.objectIds.keys()) + 1

        derivedFrom = Instance(self, placement)

        meshVertices = []
        for vertex in self.meshVertices:
            meshVertices.append(placement.getPlaced(vertex))

        volumes = []
        for volume in self.volumes:
            volumes.append(volume.getPlaced(placement))

        result = Object(objectId, meshVertices, volumes, self.color, self.metadata, derivedFrom)

        if self.carvingCornerMaximum is not None:
            result.carvingCornerMaximum = placement.getPlaced(self.carvingCornerMaximum)

        if self.carvingCornerMinimum is not None:
            result.carvingCornerMinimum = placement.getPlaced(self.carvingCornerMinimum)

        self.slicedFile.addObjects([result])
        return result

    def getLayersGroupedByZ(self):
        '''Retruns list of layerGroups groupped by layer height.'''

        if len(self.layersGroupedByZ) == 0:
            self.rebuildGroupedLayers()

        return self.layersGroupedByZ

    def rebuildGroupedLayers(self):
        '''(Re)builds layersGroupedByZ list returned by getLayersGroupedByZ method.'''

        volumes = self.volumes
        layerIndexes = [0] * len(volumes)
        self.layersGroupedByZ = []

        for (volumeIndex, layerIndex) in enumerate(layerIndexes):
            if len(volumes[volumeIndex].layers) == 0:
                layerIndexes[volumeIndex] = None

        while len([layerIndex for layerIndex in layerIndexes if layerIndex is not None]) > 0:

            nextZ = min([volumes[volumeIndex].layers[layerIndex].z for volumeIndex, layerIndex in enumerate(layerIndexes) if layerIndex is not None])

            layerGroup = []
            for volumeIndex, layerIndex in enumerate(layerIndexes):
                if layerIndex is None:
                    continue
                volume = volumes[volumeIndex]
                z = volumes[volumeIndex].layers[layerIndex].z

                if z == nextZ:
                    layerGroup.append((volume.layers[layerIndex], volume))
                    if len(volume.layers) > layerIndex + 1:
                        layerIndexes[volumeIndex] += 1
                    else:
                        layerIndexes[volumeIndex] = None

            self.layersGroupedByZ.append(layerGroup)
