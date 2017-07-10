from malcolm.core import Part, method_takes
from malcolm.tags import outport


class OdinDataPluginPart(Part):

    def __init__(self, client, index):
        name = "OdinData:" + index
        super(OdinDataPluginPart, self).__init__(name)
        self.index = index
        self.client = client

        # Provide outport to connect blocks on GUI
