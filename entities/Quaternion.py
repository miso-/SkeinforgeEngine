from math import sqrt


class Quaternion:

    def __init__(self, w, x, y, z):

        self.w = w
        self.x = x
        self.y = y
        self.z = z

        self.normalise()

    def __copy__(self):

        return Quaternion(self.w, self.x, self.y, self.z)

    def __add__(self, other):

        w = self.w + other.w
        x = self.x + other.x
        y = self.y + other.y
        z = self.z + other.z

        return Quaternion(w, x, y, z)

    def __iadd__(self, other):

        self.w += other.w
        self.x += other.x
        self.y += other.y
        self.z += other.z

        self.normalise()

        return self

    def __sub__(self, other):

        w = self.w - other.w
        x = self.x - other.x
        y = self.y - other.y
        z = self.z - other.z

        return Quaternion(w, x, y, z)

    def __iadd__(self, other):

        self.w -= other.w
        self.x -= other.x
        self.y -= other.y
        self.z -= other.z

        self.normalise()

        return self

    def __mul__(self, other):

        w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z
        x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y
        y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x
        z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w

        return Quaternion(w, x, y, z)

    def __div__(self, other):

        # Q1/Q2 = Q1*Q2.conjugate()
        return self * other.conjugate()

    def __str__(self):

        return '[w = %s, x = %s, y = %s, z = %s]' % (self.w, self.x, self.y, self.z)

    copy = __copy__

    def getDotProduct(self, other):

        return self.w * other.w + self.x * other.x + self.y * other.y + self.z * other.z

    def conjugate(self):

        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def normalise(self):

        w = self.w
        x = self.x
        y = self.y
        z = self.z

        mag2 = w * w + + x * x + y * y + z * z
        if abs(mag2 - 1) > 0.0001 and abs(mag2) > 0.0001:   # tolerance for finite floating point precision
            mag = sqrt(mag2)
            self.w /= mag
            self.x /= mag
            self.y /= mag
            self.z /= mag

        if abs(self.w) < 0.0001:
            self.w = float(0)

        if abs(self.x) < 0.0001:
            self.x = float(0)

        if abs(self.y) < 0.0001:
            self.y = float(0)

        if abs(self.z) < 0.0001:
            self.z = float(0)
