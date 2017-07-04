import os
import sys

sys.path.insert(0, "/dls_sw/work/tools/RHEL6-x86_64/odin/venv/lib/python2.7/"
                   "site-packages")
import h5py as h5

from malcolm.modules.scanning.controllers import RunnableController
from malcolm.core import method_takes, REQUIRED, Part
from malcolm.modules.ADCore.infos import DatasetProducedInfo
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta
from malcolm.modules.scanpointgenerator.vmetas import PointGeneratorMeta


@method_takes(
    "name", StringMeta("Name of part"), REQUIRED,
    "dataType", StringMeta("Data type of dataset"), REQUIRED)
class VDSWrapperPart(Part):

    # Constants for vds-gen CLI app
    VENV = "/dls_sw/work/tools/RHEL6-x86_64/odin/venv/bin/python"
    VDS_GEN = "/dls_sw/work/tools/RHEL6-x86_64/odin/vds-gen/vdsgen/app.py"
    EMPTY = "-e"
    OUTPUT = "-o"
    FILES = "-f"
    SOURCE_SHAPE = "--source-shape"
    DATA_TYPE = "--data_type"
    DATA_PATH = "-d"
    STRIPE_SPACING = "-s"
    MODULE_SPACING = "-m"
    FILL_VALUE = "-F"
    LOG_LEVEL = "-l"
    MODE = "--mode"
    SUB_FRAMES = "--sub-frames"
    INTERLEAVE = "interleave"
    RESHAPE = "reshape"
    NEW_SHAPE = "--new-shape"
    ALTERNATE = "--alternate"
    PROCESSES = "--processes"
    TOTAL_FRAMES = "--total-frames"

    # Constants for class
    CREATE = "w"
    APPEND = "a"
    READ = "r"
    ID = "/entry/NDAttributes/NDArrayUniqueId"
    SUM = "/entry/sum/sum"

    required_nodes = ["/entry/detector", "/entry/sum", "/entry/NDAttributes"]
    set_bases = ["/entry/detector", "/entry/sum"]
    default_node_tree = ["/entry/detector/axes", "/entry/detector/signal",
                         "/entry/sum/axes", "/entry/sum/signal"]

    def __init__(self, params):
        self.params = params
        super(VDSWrapperPart, self).__init__(params.name)

        self.done_when_reaches = None

        self.generator = None
        self.fill_value = None
        self.file_dir = ""
        self.file_template = ""
        self.vds_path = ""
        self.vds = None
        self.raw_paths = []
        self.raw_datasets = []

        self.data_type = params.dataType

    @RunnableController.Abort
    @RunnableController.Reset
    @RunnableController.PostRunIdle
    def abort(self, context):
        self.close_files()

    def close_files(self):
        for file_ in self.raw_datasets + [self.vds]:
            if file_ is not None and file_.id.valid:
                self.log.info("Closing file %s", file_)
                file_.close()
        self.raw_datasets = []
        self.vds = None

    def _create_dataset_infos(self, generator, filename):
        uniqueid_path = "/entry/NDAttributes/NDArrayUniqueId"
        data_path = "/entry/detector/detector"
        sum_path = "/entry/sum/sum"
        generator_rank = len(generator.axes)

        # Create the main detector data
        yield DatasetProducedInfo(
            name="EXCALIBUR.data",
            filename=filename,
            type="primary",
            rank=2 + generator_rank,
            path=data_path,
            uniqueid=uniqueid_path)

        # And the sum
        yield DatasetProducedInfo(
            name="EXCALIBUR.sum",
            filename=filename,
            type="secondary",
            rank=2 + generator_rank,
            path=sum_path,
            uniqueid=uniqueid_path)

        # Add any setpoint dimensions
        for axis in generator.axes:
            yield DatasetProducedInfo(
                name="%s.value_set" % axis, filename=filename,
                type="position_set", rank=1,
                path="/entry/detector/%s_set" % axis, uniqueid="")

    @RunnableController.Configure
    @method_takes(
        "generator", PointGeneratorMeta("Generator instance"), REQUIRED,
        "fileDir", StringMeta("File dir to write HDF files into"), REQUIRED,
        "fileTemplate", StringMeta(
            """Printf style template to generate filename relative to fileDir.
            Arguments are:
              1) %s: EXCALIBUR"""), "%s.h5",
        "fillValue", NumberMeta("int32", "Fill value for stripe spacing"), 0)
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        self.done_when_reaches = completed_steps + steps_to_do
        self.file_template = params.fileTemplate
        self.vds_path = os.path.join(
            params.fileDir, params.fileTemplate % self.OUTPUT_FILE)
        self.file_dir = params.fileDir
        self.fill_value = params.fillValue

        self.create_vds(params.generator)

        # Open the VDS
        self.vds = h5.File(
            self.vds_path, self.APPEND, libver="latest", swmr=True)

        # Return the dataset information
        dataset_infos = list(self._create_dataset_infos(
            params.generator, params.fileTemplate % self.OUTPUT_FILE))

        return dataset_infos

    def create_vds(self, generator):
        raise NotImplementedError("Must be implemented in child classes")

    def _construct_base_command(self, source_files, shape, mode, output=None):
        if output is None:
            output = self.OUTPUT_FILE

        base_command = [self.VENV, self.VDS_GEN, self.file_dir,
                        self.MODE, mode]
        # Define sources as empty and define their eventual attributes
        base_command += [self.EMPTY,
                         self.SHAPE] + shape + \
                        [self.FILES] + source_files + \
                        [self.DATA_TYPE, self.data_type]
        # Override defaults
        base_command += [self.FILL_VALUE, str(self.fill_value),
                         self.SOURCE_NODE, "/entry/detector/detector",
                         self.TARGET_NODE, "/entry/detector/detector"]
        # Define output file path
        base_command += [self.OUTPUT, output]
        base_command += [self.LOG_LEVEL, "1"]

        return base_command

    @RunnableController.PostRunReady
    @RunnableController.Seek
    def seek(self, context, completed_steps, steps_to_do, part_info):
        self.done_when_reaches = completed_steps + steps_to_do

    @RunnableController.Run
    @RunnableController.Resume
    def run(self, context, update_completed_steps):
        if not self.raw_datasets:
            self.wait_for_datasets(context)
            self.vds.swmr_mode = True
        try:
            self.log.info("Monitoring raw files until ID reaches %s",
                          self.done_when_reaches)
            while self.id < self.done_when_reaches:
                context.sleep(0.1)  # Allow while loop to be aborted
                ids = []
                for dataset in self.raw_datasets:
                    ids.append(self.get_id(dataset))
                self.update_vds(ids)

            self.log.info("ID reached: %s", self.id)
        except Exception as error:
            self.log.exception("Error in run. Message:\n%s", error.message)
            self.close_files()

    def wait_for_datasets(self, context):
        for path_ in self.raw_paths:
            self.log.info("Waiting for file %s to be created", path_)
            while not os.path.exists(path_):
                context.sleep(1)
            self.raw_datasets.append(
                h5.File(path_, self.READ, libver="latest", swmr=True))
        for dataset in self.raw_datasets:
            self.log.info("Waiting for id in file %s", dataset)
            while self.ID not in dataset:
                context.sleep(0.1)

    def update_vds(self, ids):
        raise NotImplementedError("Must be implemented in child classes")

    @property
    def id(self):
        return self.get_id(self.vds)

    def get_id(self, file_):
        if file_.id.valid and self.ID in file_:
            file_[self.ID].refresh()
            return max(file_[self.ID].value.flatten())
        else:
            self.log.warning("File %s does not exist or does not have a "
                             "UniqueIDArray, returning 0", file_)
            return 0
