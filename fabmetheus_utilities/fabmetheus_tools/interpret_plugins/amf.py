from fabmetheus_utilities.geometry.geometry_tools import face
from fabmetheus_utilities.geometry.solids import triangle_mesh
from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from entities import File, Object, Constellation, Instance, Placement
from struct import unpack
import xml.etree.ElementTree as ET


__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


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

    displacement = Vector3(x, y, z)
    rotation = Vector3(rx, ry, rz)

    return Placement(displacement, rotation)


def parsePlacementElement(instanceNode, elementName):

    element = instanceNode.find(elementName)

    if element is not None:
        return float(element.text)

    return float(0)


def parseObject(objectNode):

    objectId = int(objectNode.get('id'))
    metadata = MetaData(objectNode.findall('metadata'))
    triangleMesh = triangle_mesh.TriangleMesh()

    triangleMesh.vertexes = parseVertices(objectNode.findall('mesh/vertices/vertex'))
    volumes = parseVolumes(objectNode.findall('mesh/volume'))

    for volume in volumes:
        for triangleFace in volume.triangleFaces:
            triangleFace.index = len(triangleMesh.faces)
            triangleMesh.faces.append(triangleFace)

    return Object(objectId, triangleMesh, metadata)


def parseVertices(vertexNodes):

    vertices = []

    for vertex in vertexNodes:
        coordinates = vertex.find('coordinates')

        x = float(coordinates.find('x').text)
        y = float(coordinates.find('y').text)
        z = float(coordinates.find('z').text)

        vertices.append(Vector3(x, y, z))

    return vertices


def parseVolumes(volumeNodes):

    volumes = []

    for volumeNode in volumeNodes:
        volumes.append(Volume(volumeNode))

    return volumes


class Volume:

    def __init__(self, volumeNode):

        self.triangleFaces = []
        self.materialId = volumeNode.get('materialid')
        self.metadata = MetaData(volumeNode.findall('metadata'))

        for triangle in volumeNode.findall('triangle'):
            v1 = int(triangle.find('v1').text)
            v2 = int(triangle.find('v2').text)
            v3 = int(triangle.find('v3').text)

            triangleFace = face.Face()
            triangleFace.vertexIndexes = [v1, v2, v3]
            triangleFace.volumeRef = self
            self.triangleFaces.append(triangleFace)


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
