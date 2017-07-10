import sys

from malcolm.core.rlock import RLock
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.core import method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta

from malcolm.modules.OdinData.parts import \
    OdinDataFileWriterPart, OdinDataEigerProcessPart, OdinDataEigerDecoderPart

sys.path.insert(0, "/dls_sw/work/tools/RHEL6-x86_64/odin/odin-data-client")
from odindataclient import OdinDataClient


@method_also_takes(
    "rank", NumberMeta("int16", "Rank of this process"), REQUIRED,
    "processes", NumberMeta("int16", "Total number of processes"), REQUIRED,
    "ipAddress", StringMeta(
        "IP of server where this service is running"), REQUIRED,
    "serverRank", NumberMeta("int16", "Rank of this process on its server"), 0,
    "fanIP", StringMeta("IP of server where EigerFan is running"), REQUIRED)
class OdinDataRunnableController(RunnableController):

    use_cothread = False  # Make ZMQ happy

    DATASET = "/entry/detector/detector"

    def __init__(self, process, parts, params):
        super(OdinDataRunnableController, self).__init__(
            process, parts, params)

        self.client = OdinDataClient(params.rank, params.processes,
                                     params.ipAddress,
                                     RLock(use_cothread=False),
                                     server_rank=params.serverRank)

        self.client.configure_shared_memory()
        self.client.processor.configure_meta()

        self.plugins = []
        self.frames = None  # Size of dataset
        self.add_part(self._make_plugin_part(
            OdinDataEigerDecoderPart, self.client.FRAME_RECEIVER))
        self.add_part(self._make_plugin_part(
            OdinDataEigerProcessPart, self.client.processor.EIGER))
        self.add_part(self._make_plugin_part(
            OdinDataFileWriterPart, self.client.processor.FILE_WRITER))

    def _make_plugin_part(self, plugin, index):
        plugin_part = plugin(self.client, index)
        return plugin_part

    def _request_status(self):
        return self.client.request_status()
