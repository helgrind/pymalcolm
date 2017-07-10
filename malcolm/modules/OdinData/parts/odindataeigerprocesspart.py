from .odindatapluginpart import OdinDataPluginPart
from malcolm.tags import inport


class OdinDataEigerProcessPart(OdinDataPluginPart):

    def __init__(self, client, index):
        super(OdinDataEigerProcessPart, self).__init__(client, index)
        self.client.processor.load_plugin(index)

        # Provide inport to connect blocks on GUI, do it here for now
        self.connect_source(self.client.FRAME_RECEIVER)

    def connect_source(self, source):
        self.client.processor.connect_plugins(source, self.index)
