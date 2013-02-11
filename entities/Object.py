from fabmetheus_utilities.geometry.geometry_tools.face import Face
from fabmetheus_utilities.geometry.solids import triangle_mesh
from Instance import Instance
from Placement import Placement
import copy


class Object:

    def __init__(self, objectId, triangleMesh, metadata=None, derivedFrom=None):

        self.slicedFile = None
        self.objectId = int(objectId)
        self.metadata = metadata
        self.derivedFrom = derivedFrom
        self.triangleMesh = triangleMesh
        self.rotatedLoopLayers = []
        self.carvingCornerMaximum = None
        self.carvingCornerMinimum = None
        self.svgText = None

        self.layers = []

    def __str__(self):

        return 'Object ID: %s' % self.objectId

    def getDerivedObject(self, placement, objectId=None):

        if placement == Placement():
            return self

        if objectId is None:
            objectId = max(self.slicedFile.objectIds.keys()) + 1

        derivedFrom = Instance(self, placement)
        triangleMesh = triangle_mesh.TriangleMesh()

        for vertex in self.triangleMesh.vertexes:
            triangleMesh.vertexes.append(placement.getPlaced(vertex))

        for face in self.triangleMesh.faces:
            triangleFace = Face()
            triangleFace.vertexIndexes = copy.deepcopy(face.vertexIndexes)
            if hasattr(face, 'volumeRef'):
                triangleFace.volumeRef = face.volumeRef
            triangleFace.index = face.index
            triangleMesh.faces.append(triangleFace)

        result = Object(objectId, triangleMesh, None, derivedFrom)

        if self.carvingCornerMaximum is not None:
            result.carvingCornerMaximum = placement.getPlaced(self.carvingCornerMaximum)

        if self.carvingCornerMinimum is not None:
            result.carvingCornerMinimum = placement.getPlaced(self.carvingCornerMinimum)

        for layer in self.layers:
            result.layers.append(layer.getPlaced(placement))

        self.slicedFile.addObjects([result])
        return result
