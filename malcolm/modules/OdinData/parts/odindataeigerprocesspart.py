from .odindatapluginpart import OdinDataPluginPart
from malcolm.tags import inport


class OdinDataEigerProcessPart(OdinDataPluginPart):

    def __init__(self, client, index, parent):
        super(OdinDataEigerProcessPart, self).__init__(client, index, parent)
        self.client.load_plugin(index)

        # Provide inport to connect blocks on GUI, do it here for now
        self.connect_source(self.client.INPUT)
