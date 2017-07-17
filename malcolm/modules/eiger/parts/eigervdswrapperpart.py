import sys
from subprocess import check_call

sys.path.insert(0, "/dls_sw/work/tools/RHEL6-x86_64/odin/venv/lib/python2.7/"
                   "site-packages")
import h5py as h5

from malcolm.core import method_takes, method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import NumberMeta, StringMeta
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.modules.hdf.parts.vdswrapperpart import VDSWrapperPart, \
    configure_args

configure_args += (
    "acqID", StringMeta("Acquisition ID to configure for"), REQUIRED
)


@method_also_takes(
    "processes", NumberMeta(
        "int16", "Number of processes producing files"), REQUIRED,
    "dimensionX", NumberMeta(
        "int16", "X dimension of detector frames"), REQUIRED,
    "dimensionY", NumberMeta(
        "int16", "Y dimension of detector frames"), REQUIRED)
class EigerVDSWrapperPart(VDSWrapperPart):

    # Constants for class
    RAW_FILE_TEMPLATE = "EIGER{}.h5"
    META_FILE_TEMPLATE = "{}_meta.hdf5"
    OUTPUT_FILE = "EIGER.h5"

    def __init__(self, params):
        super(EigerVDSWrapperPart, self).__init__(params)

        self.processes = params.processes
        self.raw_files = [self.RAW_FILE_TEMPLATE.format(idx + 1)
                          for idx in range(params.processes)]
        self.dimensions = [str(params.dimensionY), str(params.dimensionX)]

    @RunnableController.Configure
    @method_takes(*configure_args)
    def configure(self, *args, **kwargs):
        super(EigerVDSWrapperPart, self).configure(*args, **kwargs)

    def create_vds(self, params):

        node_tree = ["frames", "frame_series", "frame_written",
                     "offset_written", "real_time", "size", "hash",
                     "start_time", "stop_time",
                     "config", "globalAppendix", "series",
                     "countrate", "flatfield", "mask"]
        with h5.File(self.vds_path, self.CREATE, libver="latest") as self.vds:
            for node in node_tree:
                self.vds[node] = h5.ExternalLink(
                    "./" + self.META_FILE_TEMPLATE.format(params.acqID), node)

        vds1 = "FLAT.h5"

        # Combine frames from each raw file into a flat interleaved dataset
        self.log.debug("Calling vds-gen to create interleaved VDS")
        command = self._construct_base_command(
            self.raw_files, "data", self.dimensions, self.INTERLEAVE, vds1)
        # Define interleave specific arguments
        command += [self.TOTAL_FRAMES, str(sum(params.generator.shape)),
                    self.PROCESSES, str(self.processes)]
        # Define output file path
        self.log.debug("Command: %s", command)
        check_call(command)

        # Reshape the flat VDS into the shape of the generator
        self.log.debug("Calling vds-gen to create reshaped VDS")
        command = self._construct_base_command(
            [vds1], "entry/detector/detector", self.dimensions, self.RESHAPE)
        # Define reshape specific arguments
        command += [self.NEW_SHAPE] + [str(d) for d in params.generator.shape]
        self.log.debug("Command: %s", command)
        check_call(command)

    @RunnableController.Run
    @RunnableController.Resume
    def run(self, context, update_completed_steps):
        self.log.info("Eiger VDS has nothing to update.")
        self.close_files()

    def update_vds(self, ids):
        pass

