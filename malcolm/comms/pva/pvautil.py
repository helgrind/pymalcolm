import logging

import numpy as np
import pvaccess

from malcolm.compat import str_, OrderedDict, long_
from malcolm.core import StringArray


class PvaUtil(object):
    """A utility class for PvAccess conversions"""
    pva_dtypes = {
        np.bool_: pvaccess.BOOLEAN,
        np.int8: pvaccess.BYTE,
        np.uint8: pvaccess.UBYTE,
        np.int16: pvaccess.SHORT,
        np.uint16: pvaccess.USHORT,
        np.int32: pvaccess.INT,
        np.uint32: pvaccess.UINT,
        np.int64: pvaccess.LONG,
        np.uint64: pvaccess.ULONG,
        np.float32: pvaccess.FLOAT,
        np.float64: pvaccess.DOUBLE
    }

    def dict_to_pv_object(self, dict_in, empty_allowed=True):
        structure = self.pva_structure_from_value(dict_in, empty_allowed)
        if structure:
            set_value = self.prepare_dict_set(dict_in)
            logging.debug("Set %s to %r", structure, set_value)
            structure.set(set_value)
            return structure

    def prepare_dict_set(self, dict_in):
        set_value = OrderedDict()
        for key, value in dict_in.items():
            # Turn it into something that pvaccess can just set
            if isinstance(value, StringArray):
                set_value[key] = list(value)
            elif isinstance(value, (np.number, np.ndarray)):
                set_value[key] = value.tolist()
            elif isinstance(value, dict):
                dict_set = self.prepare_dict_set(value)
                if dict_set:
                    set_value[key] = dict_set
            elif isinstance(value, list):
                if [x for x in value if isinstance(x, dict)]:
                    set_value[key] = [self.dict_to_pv_object(v) for v in value]
                else:
                    set_value[key] = value
            elif key != "typeid":
                set_value[key] = value
        return set_value

    def pva_structure_from_value(self, value, empty_allowed=False):
        # Create pv structure
        if isinstance(value, str_):
            structure = pvaccess.STRING
        elif isinstance(value, bool):
            structure = pvaccess.BOOLEAN
        elif isinstance(value, (int, long_)):
            structure = pvaccess.LONG
        elif isinstance(value, float):
            structure = pvaccess.DOUBLE
        elif isinstance(value, np.number):
            structure = self.pva_dtypes[value.dtype.type]
        elif isinstance(value, np.ndarray):
            assert len(value.shape) == 1, \
                "Expected 1d array, got {}".format(value.shape)
            structure = [self.pva_dtypes[value.dtype.type]]
        elif isinstance(value, StringArray):
            structure = [pvaccess.STRING]
        elif isinstance(value, list):
            # if not empty then determine its type
            structure = list(set(
                self.pva_structure_from_value(v) for v in value if value))
            if len(structure) == 0 or len(structure) > 1 or \
                    isinstance(structure[0], pvaccess.PvObject):
                # variant union
                structure = [()]
        elif isinstance(value, dict):
            # structure
            structure = OrderedDict()
            typeid = ""
            for k, v in value.items():
                if k == "typeid":
                    typeid = v
                else:
                    subtyp = self.pva_structure_from_value(v)
                    if subtyp is not None:
                        structure[k] = subtyp
            if structure or empty_allowed:
                structure = pvaccess.PvObject(structure, typeid)
            else:
                structure = None
        else:
            raise ValueError(
                "Cannot get pva type from %s %r" % (type(value), value))
        return structure

