from StringIO import StringIO
from fabmetheus_utilities.vector3 import Vector3
from Placement import Placement


class Instance:

    def __init__(self, object, placement=None):

        # Reference to object contained in this instance.
        self.object = object

        # Placement of the contained object.
        self.placement = placement or Placement()

    def __eq__(self, other):

        if other is None or self.__class__ != other.__class__:
            return False

        return (self.object == other.object and
                self.placement == other.placement)

    def __str__(self):

        object = ''
        object += '\n\t' + str(self.object)

        placement = ''
        for line in str(self.placement).splitlines():
            placement += '\n\t' + line

        return 'Instance:{0}{1}'.format(object, placement)
