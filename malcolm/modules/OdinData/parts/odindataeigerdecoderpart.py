from .odindatapluginpart import OdinDataPluginPart


class OdinDataEigerDecoderPart(OdinDataPluginPart):

    def __init__(self, client, index, parent):
        super(OdinDataEigerDecoderPart, self).__init__(client, index, parent)
