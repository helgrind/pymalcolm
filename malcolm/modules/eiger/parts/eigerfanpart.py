import sys

from malcolm.core.rlock import RLock
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.core import Part, method_takes, method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import StringMeta

sys.path.insert(
    0, "/dls_sw/work/tools/RHEL6-x86_64/odin/eiger-daq/tools/python")
from eigerfanclient import EigerFanClient


@method_also_takes(
    "name", StringMeta("Name of part"), REQUIRED,
    "ipAddress", StringMeta(
        "IP of server where process is running"), REQUIRED)
class EigerFanPart(Part):

    def __init__(self, params):
        super(EigerFanPart, self).__init__(params.name)

        self.frame_count = 0

        self.client = EigerFanClient(params.ipAddress,
                                     RLock(use_cothread=False))

    @RunnableController.Configure
    @method_takes()
    def configure(self, context, completed_steps, steps_to_do, part_info):
        self.frame_count = completed_steps + steps_to_do

    @RunnableController.PostRunReady
    @RunnableController.Seek
    def seek(self, context, completed_steps, steps_to_do, part_info, params):
        new_frame_count = completed_steps + steps_to_do
        self.client.rewind(new_frame_count - self.frame_count, completed_steps)
        self.frame_count = new_frame_count
