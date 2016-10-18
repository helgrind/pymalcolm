from cothread import catools

from malcolm.core.vmetas import NumberArrayMeta
from malcolm.parts.ca.capart import capart_takes
from malcolm.parts.ca.caarraypart import CAArrayPart


@capart_takes()
class CALongArrayPart(CAArrayPart):
    """ Defines a part which connects to a pv via channel access DBR_DOUBLE"""

    def create_meta(self, description, tags):
        return NumberArrayMeta("int32", description=description, tags=tags)

    def get_datatype(self):
        return catools.DBR_LONG