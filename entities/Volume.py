from fabmetheus_utilities.geometry.geometry_tools.face import Face
from fabmetheus_utilities.geometry.solids import triangle_mesh


class Volume:

    def __init__(self, triangleFaces, color=None, materialId=None, metadata=None):

        self.parentObject = None
        self.color = color
        self.materialId = materialId
        self.metadata = metadata

        self.triangleMesh = triangle_mesh.TriangleMesh()
        self.triangleMesh.faces = triangleFaces
        self.rotatedLoopLayers = []
        self.carvingCornerMaximum = None        # TODO: Currently holds dimensions
        self.carvingCornerMinimum = None        # for whole object, not volume.
        self.svgText = None

        self.layers = []

    def getPlaced(self, placement):

        triangleFaces = []
        for face in self.triangleMesh.faces:
            triangleFace = Face()
            triangleFace.vertexIndexes = face.vertexIndexes[:]
            triangleFace.index = face.index
            triangleFaces.append(triangleFace)

        result = Volume(triangleFaces, self.color, self.materialId, self.metadata)

        for layer in self.layers:
            result.layers.append(layer.getPlaced(placement))

        return result
