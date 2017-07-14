from .odindatapluginpart import OdinDataPluginPart


class OdinDataEigerDecoderPart(OdinDataPluginPart):

    def __init__(self, client, parent):
        index = client.INPUT
        super(OdinDataEigerDecoderPart, self).__init__(client, index, parent)
