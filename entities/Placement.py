'''Quaternion transformations code is based on informations provided at http://www.euclideanspace.com/'''

from fabmetheus_utilities.vector3 import Vector3
from Quaternion import Quaternion
import math
import logging

name = 'Placement'
logger = logging.getLogger(name)


def sin(angle):

    angle %= 360

    if angle < 0:
        angle -= 360

    if angle == 0 or angle == 180:
        return float(0)
    if angle == 90:
        return float(1)
    if angle == 270:
        return float(-1)

    return math.sin(math.radians(angle))


def cos(angle):

    angle %= 360

    if angle < 0:
        angle -= 360

    if angle == 0:
        return float(1)
    if angle == 90 or angle == 270:
        return float(0)
    if angle == 180:
        return float(-1)

    return math.cos(math.radians(angle))


class Placement:

    def __init__(self, displacement=None, rotation=None):

        self.displacement = None
        self.rotationQuat = None
        self.rotationMatrix = None

        self.setDisplacement(displacement)
        self.setRotation(rotation)

    def __mul__(self, other):

        disp = self.displacement + self.getRotated(other.displacement)
        quat = self.rotationQuat * other.rotationQuat

        return Placement(disp, quat)

    def __imul__(self, other):

        self.displacement += self.getRotated(other.displacement)
        self.rotationQuat *= other.rotationQuat
        self.rotationMatrix = None

        return self

    def __div__(self, other):

        quat = self.rotationQuat / other.rotationQuat
        result = Placement(Vector3(0, 0, 0), quat)
        disp = self.displacement - result.getRotated(other.displacement)
        result.setDisplacement(disp)

        return result

    def __idiv__(self, other):

        self.rotationQuat /= other.rotationQuat
        self.displacement -= self.getRotated(other.displacement)
        self.rotationMatrix = None

        return self

    def __eq__(self, other):

        if other is None or self.__class__ != other.__class__:
            return False

        return self.displacement == other.displacement and self.rotationQuat.getDotProduct(other.rotationQuat) == 1

    def __str__(self):

        return 'Displacement: [%s, %s, %s]\nRotation: %s' % (self.displacement.x, self.displacement.y,
                                                             self.displacement.z, self.rotationQuat)

    def xyz2quat(self):

        # Converts rotation given in Euler angles in x, y, z order to quaternion
        # equivalent to Qz * Qy * Qx

        cx = cos(self.xyzRotation.x / 2)
        cy = cos(self.xyzRotation.y / 2)
        cz = cos(self.xyzRotation.z / 2)
        sx = sin(self.xyzRotation.x / 2)
        sy = sin(self.xyzRotation.y / 2)
        sz = sin(self.xyzRotation.z / 2)

        w = cx * cy * cz + sx * sy * sz
        x = sx * cy * cz - cx * sy * sz
        y = cx * sy * cz + sx * cy * sz
        z = - sx * sy * cz + cx * cy * sz

        self.rotationQuat = Quaternion(w, x, y, z)

    def quat2matrix(self):

        w = self.rotationQuat.w
        x = self.rotationQuat.x
        y = self.rotationQuat.y
        z = self.rotationQuat.z

        self.rotationMatrix = [
            [1 - 2 * y * y - 2 * z * z, 2 * x * y - 2 * w * z,      2 * x * z + 2 * w * y],
            [2 * x * y + 2 * w * z,     1 - 2 * x * x - 2 * z * z,  2 * y * z - 2 * w * x],
            [2 * x * z - 2 * w * y,     2 * y * z + 2 * w * x,      1 - 2 * x * x - 2 * y * y]
        ]

    def setDisplacement(self, displacement):

        if displacement is None:
            displacement = Vector3(0, 0, 0)

        self.displacement = displacement.copy()

    def getDisplacement(self):

        return self.displacement

    def setRotation(self, rotation):

        if rotation is None:
            rotation = Vector3(0, 0, 0)

        if isinstance(rotation, Vector3):
            self.xyzRotation = rotation.copy()
            self.xyz2quat()
        elif isinstance(rotation, Quaternion):
            self.rotationQuat = rotation.copy()
            self.rotationQuat.normalise()
        else:
            raise Exception()

        self.rotationMatrix = None

    def getRotation(self):

        return self.rotationQuat

    def rotatesOutOfXYPlane(self):

        return (self.rotationQuat.x != float(0) or self.rotationQuat.y != float(0))

    def getRotated(self, vector):

        if not self.rotatesOutOfXYPlane() and self.rotationQuat.z == 0:
            return vector

        if self.rotationMatrix is None:
            self.quat2matrix()

        rotationMatrix = self.rotationMatrix

        if isinstance(vector, complex):
            if self.rotatesOutOfXYPlane():
                logger.error('Cann\'t  rotate "complex" out of XY plane!')
                return None

            resultX = vector.real * rotationMatrix[0][0] + vector.imag * rotationMatrix[0][1]
            resultY = vector.real * rotationMatrix[1][0] + vector.imag * rotationMatrix[1][1]

            return complex(resultX, resultY)

        # Performs rotationMatrix * vector (1x3 matrix) matrix multiplication.
        resultX = vector.x * rotationMatrix[0][0] + vector.y * rotationMatrix[0][1] + vector.z * rotationMatrix[0][2]
        resultY = vector.x * rotationMatrix[1][0] + vector.y * rotationMatrix[1][1] + vector.z * rotationMatrix[1][2]
        resultZ = vector.x * rotationMatrix[2][0] + vector.y * rotationMatrix[2][1] + vector.z * rotationMatrix[2][2]

        return Vector3(resultX, resultY, resultZ)

    def getDisplaced(self, vector):

        if isinstance(vector, complex):
            if self.displacement.z != 0:
                logger.error('Displacement along z axis must be 0 to work with complex! disp= %s' % self.displacement)
                return None
            vector3 = Vector3(vector.real, vector.imag, 0)
            result3 = self.displacement + vector3
            return complex(result3.x, result3.y)

        return self.displacement + vector

    def getPlaced(self, vector):

        return self.getDisplaced(self.getRotated(vector))
