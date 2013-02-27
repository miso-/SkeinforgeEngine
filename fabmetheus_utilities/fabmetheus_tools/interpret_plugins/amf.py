from fabmetheus_utilities.geometry.geometry_tools import face
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from entities import File, Volume, Object, Constellation, Instance, Placement
from struct import unpack
import xml.etree.ElementTree as ET
from math import sqrt
from config import config


__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

unitsConversionDict = {'milimeter': 1,
                       'meter': 1000,
                       'micron': 0.001,
                       'inch': 25.4,
                       'feet': 304.8}

unitScaleFactor = 1


def getCarving(slicedFile):
    "Get the triangle mesh for the stl file."

    parseFile(slicedFile)
    createFlatTopology(slicedFile)


def createFlatTopology(slicedFile):

    topLevelConstellations = slicedFile.getTopLevelConstellations()

    instances = []
    for topLevelConstellation in topLevelConstellations:
        instances += topLevelConstellation.getInstances(recursive=True)

    slicedFile.printbed.addInstances(instances)

    # Look if there are any objects left, that are not part of constellation hierarchy
    # and put them into "master" printbed constellation.
    referencedObjects = slicedFile.printbed.getObjects()
    for object in slicedFile.objects:
        if object not in referencedObjects:
            slicedFile.printbed.addInstances([Instance(object)])


def parseFile(slicedFile):

    if slicedFile.fileName == '':
        return

    fileNode = ET.parse(slicedFile.fileName).getroot()

    unit = fileNode.get('unit')
    global unitScaleFactor
    unitScaleFactor = unitsConversionDict.get(unit, 1)

    objectIds = {}
    objects = []
    constellations = []
    materials = []
    textures = []
    metadata = MetaData(fileNode.findall('metadata'))

    for objectNode in fileNode.findall('object'):
        object = parseObject(objectNode)
        objects.append(object)
        objectIds[object.objectId] = object

    for constellationNode in fileNode.findall('constellation'):
        constellation = parseConstellation(constellationNode)
        constellations.append(constellation)
        objectIds[constellation.objectId] = constellation

    for textureNode in fileNode.findall('texture'):
        texture = Texture(textureNode)
        textures[texture.id] = texture

    # Replace temporary used objectIds with memory references.
    for constellation in constellations:
        for instance in constellation.instances:
            instance.object = objectIds[instance.object]

    slicedFile.addObjects(objects)
    slicedFile.addConstellations(constellations)
    slicedFile.addTextures(textures)
    slicedFile.setMetadata(metadata)
    slicedFile.addMaterials(materials)


def parseConstellation(constellationNode):

    objectId = int(constellationNode.get('id'))
    instances = []

    for instanceNode in constellationNode.findall('instance'):
        instance = parseInstance(instanceNode)
        instances.append(instance)

    return Constellation(objectId, instances)


def parseInstance(instanceNode):

    objectId = int(instanceNode.get('objectid'))
    placement = parsePlacement(instanceNode)

    # Temporary use objectId instead of memory reference.
    return Instance(objectId, placement)


def parsePlacement(instanceNode):

    x = parsePlacementElement(instanceNode, 'deltax')
    y = parsePlacementElement(instanceNode, 'deltay')
    z = parsePlacementElement(instanceNode, 'deltaz')

    rx = parsePlacementElement(instanceNode, 'rx')
    ry = parsePlacementElement(instanceNode, 'ry')
    rz = parsePlacementElement(instanceNode, 'rz')

    displacement = Vector3(x, y, z) * unitScaleFactor
    rotation = Vector3(rx, ry, rz)

    return Placement(displacement, rotation)


def parsePlacementElement(instanceNode, elementName):

    element = instanceNode.find(elementName)

    if element is not None:
        return float(element.text)

    return float(0)


def parseObject(objectNode):

    objectId = int(objectNode.get('id'))
    vertices = parseVertices(objectNode.findall('mesh/vertices/vertex'))
    volumes = parseVolumes(objectNode.findall('mesh/volume'))
    color = None
    metadata = MetaData(objectNode.findall('metadata'))

    parseEdges(objectNode.findall('mesh/vertices/edge'), vertices)

    for volume in volumes:
        curvedTriangles = []
        plainTriangles = []
        triangleMesh = triangle_mesh.TriangleMesh()
        for triangleFace in volume.triangleMesh.faces:
            if isCurvedTriange(triangleFace, vertices):
                curvedTriangles.append(triangleFace)
            else:
                plainTriangles.append(triangleFace)

        for triangleFace in curvedTriangles:
            triangles = divideTriangle(triangleFace, vertices, config.getint('export', 'amf.curved.triangles.subdivision.depth'))
            for triangle in triangles:
                triangle.index = len(triangleMesh.faces)
                triangleMesh.faces.append(triangle)

        for triangleFace in plainTriangles:
            if config.getint('export', 'amf.curved.triangles.subdivision.depth') >= 0:
                for triangle in retesselate(triangleFace, vertices):
                    triangle.index = len(triangleMesh.faces)
                    triangleMesh.faces.append(triangle)
            else:
                triangleFace.index = len(triangleMesh.faces)
                triangleMesh.faces.append(triangleFace)

        volume.triangleMesh = triangleMesh

    meshVertices = [vertex.coordinates for vertex in vertices]

    return Object(objectId, meshVertices, volumes, color, metadata)


def parseVolumes(volumeNodes):

    volumes = []

    for volumeNode in volumeNodes:

        triangleFaces = []
        color = None
        materialId = volumeNode.get('materialId')
        metadata = MetaData(volumeNode.findall('metadata'))

        for triangle in volumeNode.findall('triangle'):
            v1 = int(triangle.find('v1').text)
            v2 = int(triangle.find('v2').text)
            v3 = int(triangle.find('v3').text)

            triangleFace = face.Face()
            triangleFace.vertexIndexes = [v1, v2, v3]
            triangleFaces.append(triangleFace)

        volumes.append(Volume(triangleFaces, color, materialId, metadata))

    return volumes


def parseVertices(vertexNodes):

    vertices = []

    for vertexNode in vertexNodes:

        coordinatesNode = vertexNode.find('coordinates')
        x = float(coordinatesNode.find('x').text)
        y = float(coordinatesNode.find('y').text)
        z = float(coordinatesNode.find('z').text)
        coordinates = Vector3(x, y, z) * unitScaleFactor

        normalNode = vertexNode.find('normal')
        if normalNode is not None:
            nx = float(normalNode.find('nx').text)
            ny = float(normalNode.find('ny').text)
            nz = float(normalNode.find('nz').text)
            normal = Vector3(nx, ny, nz)

            # Normalize normal vector.
            mag2 = normal.magnitudeSquared()
            if mag2 - 1 > 0.0001 or mag2 - 1 < 0.0001:
                if mag2 != float(0):
                    normal /= sqrt(mag2)
                else:
                    normal = None
        else:
            normal = None

        vertices.append(Vertex(coordinates, normal))

    return vertices


def parseEdges(edgeNodes, vertices):

    edges = []

    for edgeNode in edgeNodes:
        v1Index = int(edgeNode.find('v1').text)
        dx1 = float(edgeNode.find('dx1').text)
        dy1 = float(edgeNode.find('dy1').text)
        dz1 = float(edgeNode.find('dz1').text)
        t1 = Vector3(dx1, dy1, dz1) * unitScaleFactor

        v2Index = int(edgeNode.find('v2').text)
        dx2 = float(edgeNode.find('dx2').text)
        dy2 = float(edgeNode.find('dy2').text)
        dz2 = float(edgeNode.find('dz2').text)
        t2 = Vector3(dx2, dy2, dz2) * unitScaleFactor

        storeEdge(Edge(v1Index, t1, v2Index, t2), vertices)


def storeEdge(edge, vertices, scale=True):
    '''Stores edge into vertices'''

    if scale:
        # Scale tangents to the length of edge.
        edgeLength = (vertices[edge.v1Index].coordinates - vertices[edge.v0Index].coordinates).magnitude()
        if edge.t0 is not None:
            edge.t0 = edge.t0.getNormalized() * edgeLength
        if edge.t1 is not None:
            edge.t1 = edge.t1.getNormalized() * edgeLength

    # edge.v0Index is by convention vertex with lower index than edge.v1Index so
    # edge is always stored at vertex with lower index.

    vertices[edge.v0Index].edges.append(edge)


def getEdge(index1, index2, vertices):
    '''Returns edge from point A to B'''

    if index1 < index2:  # Edge is by convention stored at vertex with lower index.
        storedAtIndex = index1
        toIndex = index2
    else:
        storedAtIndex = index2
        toIndex = index1

    for edge in vertices[storedAtIndex].edges:
        if edge.v1Index == toIndex:
            return edge

    return None


def isCurvedTriange(triangle, vertices):
    '''Returns true if "triangle" is curved triangle'''

    for vertexIndex in triangle.vertexIndexes:
        if vertices[vertexIndex].normal:
            return True
        for edge in vertices[vertexIndex].edges:
            if edge.v0Index in triangle.vertexIndexes:
                return True

    return False


def retesselate(triangle, vertices, recursive=True):

    # build vertex list

    triangleVertices = []
    for vertexTIndex in range(3):
        vertexAt = None
        edge = getEdge(triangle.vertexIndexes[vertexTIndex], triangle.vertexIndexes[(vertexTIndex + 1) % 3], vertices)
        if edge is not None:
            vertexAt = edge.vertexAt
        triangleVertices.append(triangle.vertexIndexes[vertexTIndex])
        triangleVertices.append(vertexAt)

    # Splits triangle in two along the line coming from first edge mid-point encounterd to opposite triangle vertex.
    triangles = []
    for middleVertexIndex in [1, 3, 5]:
        middleVertex = triangleVertices[middleVertexIndex]
        if middleVertex is None:
            continue
        oppositeVertex = triangleVertices[(middleVertexIndex + 3) % 6]
        prevVertex = triangleVertices[(middleVertexIndex - 1) % 6]
        nextVertex = triangleVertices[(middleVertexIndex + 1) % 6]
        triangle = face.Face()
        triangle.vertexIndexes.append(prevVertex)
        triangle.vertexIndexes.append(middleVertex)
        triangle.vertexIndexes.append(oppositeVertex)
        triangles.append(triangle)
        triangle = face.Face()
        triangle.vertexIndexes.append(middleVertex)
        triangle.vertexIndexes.append(nextVertex)
        triangle.vertexIndexes.append(oppositeVertex)
        triangles.append(triangle)

    result = []
    for t in triangles:
        result += retesselate(t, vertices)

    if len(result) == 0:
        result.append(triangle)

    return result


def calcNormal(atVertexIndex, vertices, triangle):
    '''Calculates normal to triangle surface at given vertex'''

    thisVertexTIndex = triangle.vertexIndexes.index(atVertexIndex)
    prevVertexTIndex = (thisVertexTIndex + 2) % 3
    nextVertexTIndex = (thisVertexTIndex + 1) % 3

    prevVertexIndex = triangle.vertexIndexes[prevVertexTIndex]
    nextVertexIndex = triangle.vertexIndexes[nextVertexTIndex]

    prevVertex = vertices[prevVertexIndex].coordinates
    thisVertex = vertices[atVertexIndex].coordinates
    nextVertex = vertices[nextVertexIndex].coordinates

    edgeThisPrev = getEdge(atVertexIndex, prevVertexIndex, vertices)
    tangentPrev = None
    if edgeThisPrev is not None:
        tangentPrev = edgeThisPrev.getTangent(atVertexIndex)
        if prevVertexIndex > atVertexIndex and tangentPrev is not None:
            tangentPrev = -tangentPrev
    if tangentPrev is None:
        tangentPrev = thisVertex - prevVertex

    edgeThisNext = getEdge(atVertexIndex, nextVertexIndex, vertices)
    tangentNext = None
    if edgeThisNext is not None:
        tangentNext = edgeThisNext.getTangent(atVertexIndex)
        if atVertexIndex > nextVertexIndex and tangentNext is not None:
            tangentNext = -tangentNext
    if tangentNext is None:
        tangentNext = nextVertex - thisVertex

    normal = tangentPrev.cross(tangentNext)

    return normal.getNormalized()


def calcTangent(indexA, normalA, indexB, vertices):
    '''Calculates tangent at vertexA to the edge connecting vertexA with vertexB'''

    if indexA < indexB:
        vectorAB = vertices[indexB].coordinates - vertices[indexA].coordinates
    else:
        vectorAB = vertices[indexA].coordinates - vertices[indexB].coordinates

    tangentABRaw = (normalA.cross(vectorAB)).cross(normalA)

    tangentAB = vectorAB.magnitude() * tangentABRaw.getNormalized()

    return tangentAB


def divideTriangle(triangle, vertices, depth):
    '''Recursively divides curved triangle into subtriangles'''

    # See Annex 3 - Formulae for interpolating a curved triangular patch, of ASTM F2915 standard.
    # V0.48 draft is available at http://amf.wikispaces.com/file/detail/AMF_V0.48.pdf

    if depth <= 0:
        return [triangle]
    depth -= 1

    newVertexIndexes = []

    for vertexTIndex in range(3):

        AIndex = triangle.vertexIndexes[vertexTIndex]
        BIndex = triangle.vertexIndexes[(vertexTIndex + 1) % 3]

        edge = getEdge(AIndex, BIndex, vertices)
        if edge is None:
            edge = Edge(AIndex, None, BIndex, None)
            storeEdge(edge, vertices)

        v0Index = edge.v0Index
        v1Index = edge.v1Index

        v0 = vertices[v0Index].coordinates
        v1 = vertices[v1Index].coordinates
        n0 = vertices[v0Index].normal
        n1 = vertices[v1Index].normal

        if n0 is None:
            n0 = calcNormal(v0Index, vertices, triangle)

        if n1 is None:
            n1 = calcNormal(v1Index, vertices, triangle)

        if edge.vertexAt is None:
            # This edge was not split yet.

            t0 = edge.t0
            if t0 is None:
                t0 = calcTangent(v0Index, n0, v1Index, vertices)
                edge.t0 = t0

            t1 = edge.t1
            if t1 is None:
                t1 = calcTangent(v1Index, n1, v0Index, vertices)
                edge.t1 = t1

            # v01 = h(s) for s = 0.5
            # h(s) = (2s^3-3s^2+1)v0 + (s^3-2s^2+s)t0 + (-2s^3+3s^2)v1 + (s^3-s^2)t1
            # h(0.5) = (0.5)v0 + (0.125)t0 + (0.5)v1 + (-0.125)t1

            v01 = (0.5) * v0 + (0.125) * t0 + (0.5) * v1 + (-0.125) * t1

            # t01 = t(s) for s = 0.5
            # t(s) = (6s^2-6s)v0 + (3s^2-4s+1)t0 + (-6s^2+6s)v1 + (3s^2-2s)t1
            # t(0.5) = (-1.5)v0 + (-0.25)t0 + (1.5)v1 + (-0.25)t1

            t01 = (-1.5) * v0 + (-0.25) * t0 + (1.5) * v1 + (-0.25) * t1

            n01 = None

            vertex01Index = len(vertices)
            vertex01 = Vertex(v01)
            vertices.append(vertex01)

            storeEdge(Edge(v0Index, t0, vertex01Index, t01), vertices)
            storeEdge(Edge(v1Index, -t1, vertex01Index, -t01), vertices)
            edge.vertexAt = vertex01Index

        else:
            # This edge was already split when neighbouring triangle was processed. Existing data may be
            # reused.

            v01 = vertices[edge.vertexAt].coordinates
            t01 = getEdge(v0Index, edge.vertexAt, vertices).getTangent(edge.vertexAt)
            n01 = vertices[edge.vertexAt].normal
            vertex01Index = edge.vertexAt
            vertex01 = vertices[vertex01Index]

        if n01 is None:
            # The normal at the subdivided center point shall be linearly interpolated from the two endpoint normals then
            # forced to the nearest perpendicular direction from the calculated center point edge tangent.
            # - Jonathan Hiller, https://groups.google.com/forum/?fromgroups=#!topic/stl2/uIIiRVorbMU

            n01 = 0.5 * (n0 + n1)
            n01 = t01.cross(n01.cross(t01))
            vertex01.normal = n01.getNormalized()

        newVertexIndexes.append(vertex01Index)

    newTriangles = []

    # create 3x "vertex" triangles
    for vertexTIndex in range(3):
        v1 = triangle.vertexIndexes[vertexTIndex]
        v2 = newVertexIndexes[vertexTIndex]
        v3 = newVertexIndexes[(vertexTIndex + 2) % 3]
        triangleFace = face.Face()
        triangleFace.vertexIndexes = [v1, v2, v3]
        newTriangles.append(triangleFace)

    # create "center" triangle
    v1 = newVertexIndexes[0]
    v2 = newVertexIndexes[1]
    v3 = newVertexIndexes[2]
    triangleFace = face.Face()
    triangleFace.vertexIndexes = [v1, v2, v3]
    newTriangles.append(triangleFace)

    result = []

    for newTriangle in newTriangles:
        result += divideTriangle(newTriangle, vertices, depth)

    for vertexIndex in newVertexIndexes:
        vertices[vertexIndex].normal = None

    return result


class Edge:

    def __init__(self, v0Index, t0, v1Index, t1, vertexAt=None):

        if v0Index < v1Index:
            self.v0Index = v0Index
            self.t0 = t0
            self.v1Index = v1Index
            self.t1 = t1
        else:
            self.v0Index = v1Index
            self.t0 = t1
            self.v1Index = v0Index
            self.t1 = t0

        self.vertexAt = vertexAt  # Holds index of vertex, calc. by interpolation, laying on this edge.

    def getTangent(self, atIndex):

        if atIndex == self.v0Index:
            return self.t0
        elif atIndex == self.v1Index:
            return self.t1
        else:
            return None


class Vertex:

    def __init__(self, coordinates, normal=None):

        self.coordinates = coordinates
        self.normal = normal
        self.edges = []


class MetaData:

    def __init__(self, metadataNodes):

        self.metaData = {}

        for metadataNode in metadataNodes:
            key = metadataNode.get('type')
            value = metadataNode.text
            self.metaData[key] = value

    def __str__(self):
        '''Get the string representation.'''
        output = ''
        for key in self.metaData.keys():
            output += str(key) + ': ' + str(self.metaData[key]) + '\n'

        return output


class Texture:

    def __init__(self, textureNode):

        self.id = textureNode.get('id')
        self.width = textureNode.get('width')
        self.height = textureNode.get('height')
        self.depth = textureNode.get('depth')
        self.bitmap = map(ord, binascii.a2b_base64(textureNode.text))
