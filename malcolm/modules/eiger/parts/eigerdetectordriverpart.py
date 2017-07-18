from malcolm.core import method_takes, REQUIRED
from malcolm.modules.builtin.vmetas import StringMeta, ChoiceMeta
from malcolm.modules.ADCore.parts import ExposureDetectorDriverPart
from malcolm.modules.ADCore.parts.detectordriverpart import configure_args
from malcolm.modules.scanning.controllers import RunnableController

configure_args += (
    "acqID", StringMeta("Acquisition ID to configure for"), REQUIRED,
    "compression", ChoiceMeta("Compression type", ("LZ4", "BSLZ4")), None
)


class EigerDetectorDriverPart(ExposureDetectorDriverPart):

    ACQ_ID_TEMPLATE = r"{{\"acqID\": \"{}\"}}"
    COMPRESSION_TYPES = dict(BSLZ4="BS LZ4", LZ4="LZ4")

    def is_hardware_triggered(self, child):
        return False

    @RunnableController.Configure
    @method_takes(*configure_args)
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        super(EigerDetectorDriverPart, self).configure(
            context, completed_steps, steps_to_do, part_info, params)

    def setup_detector(self, child, completed_steps, steps_to_do, params=None):
        fs = super(EigerDetectorDriverPart, self).setup_detector(
            child, completed_steps, steps_to_do, params=params)
        exposure = params.generator.duration - self.readout_time.value
        values = dict(compression=self.COMPRESSION_TYPES[params.compression],
                      acquisitionID=self.ACQ_ID_TEMPLATE.format(params.acqID),
                      FWEnable="No",
                      streamEnable="Yes",
                      callbackSource="None",
                      acquirePeriod=exposure)
        fs += child.put_attribute_values_async(values)
        return fs
