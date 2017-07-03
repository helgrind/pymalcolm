import os
import sys
from subprocess import check_call

sys.path.insert(0, "/dls_sw/work/tools/RHEL6-x86_64/odin/venv/lib/python2.7/"
                   "site-packages")
import h5py as h5

from malcolm.core import method_also_takes, REQUIRED
from malcolm.modules.builtin.vmetas import NumberMeta

from malcolm.modules.hdf.parts.vdswrapperpart import VDSWrapperPart


@method_also_takes(
    "stripeHeight", NumberMeta("int16", "Height of stripes"), REQUIRED,
    "stripeWidth", NumberMeta("int16", "Width of stripes"), REQUIRED)
class ExcaliburVDSWrapperPart(VDSWrapperPart):

    # Constants for class
    RAW_FILE_TEMPLATE = "FEM{}"
    OUTPUT_FILE = "EXCALIBUR"

    def __init__(self, params):
        super(ExcaliburVDSWrapperPart, self).__init__(params)

        self.stripe_height = params.stripeHeight
        self.stripe_width = params.stripeWidth
        self.fems = [1, 2, 3, 4, 5, 6]

    def create_vds(self, file_dir, generator, fill_value, file_template):
        self.log.debug("Creating ExternalLinks from VDS to FEM1.h5")
        self.vds_path = os.path.join(
            file_dir, file_template % self.OUTPUT_FILE)
        raw_file_path = file_template % self.RAW_FILE_TEMPLATE.format(1)
        node_tree = list(self.default_node_tree)
        for axis in generator.axes:
            for base in self.set_bases:
                node_tree.append(base + "/{}_set".format(axis))
                node_tree.append(base + "/{}_set_indices".format(axis))

        with h5.File(self.vds_path, self.CREATE, libver="latest") as self.vds:
            for node in self.required_nodes:
                self.vds.require_group(node)
            for node in node_tree:
                self.vds[node] = h5.ExternalLink(raw_file_path, node)

            # Create placeholder id and sum datasets
            initial_dims = tuple([1 for _ in generator.shape])
            initial_shape = initial_dims + (1, 1)
            max_shape = generator.shape + (1, 1)
            self.vds.create_dataset(self.ID, initial_shape,
                                    maxshape=max_shape, dtype="int32")
            self.vds.create_dataset(self.SUM, initial_shape,
                                    maxshape=max_shape, dtype="float64")

        self.log.debug("Calling vds-gen to create dataset in VDS")
        files = [file_template % self.RAW_FILE_TEMPLATE.format(fem)
                 for fem in self.fems]
        shape = [str(d) for d in generator.shape] + \
                [str(self.stripe_height), str(self.stripe_width)]
        # Base arguments
        command = [self.VENV, self.VDS_GEN, file_dir]
        # Define empty and required arguments to do so
        command += [self.EMPTY,
                    self.FILES] + files + \
                   [self.SHAPE] + shape + \
                   [self.DATA_TYPE, self.data_type]
        # Override default spacing and data path
        command += [self.STRIPE_SPACING, "0",
                    self.MODULE_SPACING, "121",
                    self.FILL_VALUE, str(fill_value),
                    self.SOURCE_NODE, "/entry/detector/detector",
                    self.TARGET_NODE, "/entry/detector/detector"]
        # Define output file path
        command += [self.OUTPUT, file_template % self.OUTPUT_FILE]
        command += [self.LOG_LEVEL, "1"]  # str(self.log.level / 10)]
        self.log.info("Command: %s", command)
        check_call(command)

    def update_vds(self, ids):
        if min(ids) > self.id:
            self.log.info("Raw ID changed: %s - "
                          "Updating VDS ID and Sum", min(ids))
            idx = ids.index(min(ids))
            self._update_id(idx)
            self._update_sum(idx)

    def _update_id(self, min_dataset):
        min_id = self.raw_datasets[min_dataset][self.ID]

        self.log.debug("ID shape:\n%s", min_id.shape)
        self.vds[self.ID].resize(min_id.shape)
        self.vds[self.ID][...] = min_id
        self.vds[self.ID].flush()

    def _update_sum(self, min_dataset):
        min_sum = self.raw_datasets[min_dataset][self.SUM].value

        # Slice the full the extent of the minimum dataset from each dataset
        # Some nodes could be a row ahead meaning the shapes are mismatched
        min_shape = tuple([slice(0, axis_size)
                           for axis_size in min_sum.shape])
        sum_ = 0
        for dataset in self.raw_datasets:
            dataset[self.SUM].refresh()
            sum_ += dataset[self.SUM].value[min_shape]

        # Re-insert -1 for incomplete indexes using mask from minimum dataset
        mask = min_sum < 0
        sum_[mask] = -1

        self.log.debug("Sum shape:\n%s", sum_.shape)
        self.vds[self.SUM].resize(sum_.shape)
        self.vds[self.SUM][...] = sum_
        self.vds[self.SUM].flush()
