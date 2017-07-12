import sys
import math as m

from malcolm.core.rlock import RLock
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.core import Part, method_takes, method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import StringMeta
from malcolm.modules.scanpointgenerator.vmetas import PointGeneratorMeta

sys.path.insert(
    0, "/dls_sw/work/tools/RHEL6-x86_64/odin/odin-data/tools/python")
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
        self.acq_id = None

    @RunnableController.Configure
    @method_takes(
        "fileDir", StringMeta("File dir to write HDF files into"), REQUIRED,
        "generator", PointGeneratorMeta("Generator instance"), REQUIRED,
        "acqID", StringMeta("Acquisition ID to configure for"), REQUIRED)
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        flush_time = 1
        if params.generator.duration > flush_time:
            # We are going slower than 1/flush_time Hz, so flush every frame
            frames_between_flushes = 1
        else:
            # Limit update rate to be every flush_time seconds
            frames_between_flushes = int(m.ceil(
                flush_time / params.generator.duration))
            # But make sure we flush in this round of frames
            frames_between_flushes = min(
                steps_to_do, frames_between_flushes)
        self.client.configure_output_dir(params.fileDir, params.acqID)
        self.client.configure_flush_rate(frames_between_flushes, params.acqID)

        self.acq_id = params.acqID

    @RunnableController.Abort
    @RunnableController.Reset
    def stop(self, context):
        self.client.stop(self.acq_id)
