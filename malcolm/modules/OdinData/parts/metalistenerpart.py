import sys

from malcolm.core.rlock import RLock
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.core import Part, method_takes, method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta

sys.path.insert(0, "/dls_sw/work/tools/RHEL6-x86_64/odin/odin-data-client")
from odindataclient import MetaListenerClient


@method_also_takes(
    "name", StringMeta("Name of part"), REQUIRED,
    "ipAddress", StringMeta(
        "IP of server where process is running"), REQUIRED)
class MetaListenerPart(Part):

    def __init__(self, params):
        super(MetaListenerPart, self).__init__(params.name)

        self.client = MetaListenerClient(params.ipAddress,
                                         RLock(use_cothread=False))

    # Provide as outport
    def request_output_file(self):
        self.client.request_output_file()

    # @RunnableController.Configure
    # @method_takes(
    #     "flushRate", NumberMeta(
    #         "int16", "Number of frames between hdf flushes"), REQUIRED)
    # def configure(self, params):
    #     # For specific acq id
    #     self.client.configure_flush_rate(params.flushRate)
