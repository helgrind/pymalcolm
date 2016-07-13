from malcolm.core.scalarmeta import ScalarMeta
from malcolm.core.serializable import Serializable


@Serializable.register_subclass("malcolm:core/StringArrayMeta:1.0")
class StringArrayMeta(ScalarMeta):
    """Meta object containing information for a string array"""

    def __init__(self, name, description):
        super(StringArrayMeta, self).__init__(
            name=name, description=description)

    def validate(self, value):
        """
        Verify value can be iterated and cast elements to strings

        Args:
            value (iterable): value to be validated

        Returns:
            List of Strings or None if value is None
        """
        if value is None:
            return None
        if not hasattr(value, "__iter__"):
            raise ValueError("%s is not iterable" % value)
        validated = [str(x) if x is not None else None for x in value]
        if None in validated:
            raise ValueError("Array elements can not be null")
        return validated
