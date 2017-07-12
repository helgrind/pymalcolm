from malcolm.core import method_takes, REQUIRED
from malcolm.modules.builtin.vmetas \
    import StringMeta, StringArrayMeta, NumberMeta, NumberArrayMeta, ChoiceMeta
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.tags import inport

from .odindatapluginpart import OdinDataPluginPart


class OdinDataFileWriterPart(OdinDataPluginPart):

    DATA_TYPES = dict(uint8=0, uint16=1, uint32=2)
    COMPRESSION_TYPES = dict(LZ4=1, BSLZ4=2)

    def __init__(self, client, index):
        super(OdinDataFileWriterPart, self).__init__(client, index)
        self.client.load_file_writer_plugin(index)
        self.client.configure_file_process()

        # Provide inport to connect blocks on GUI, do it here for now
        self.connect_source(self.client.EIGER)

        self.done_when_reaches = 0

    @RunnableController.Configure
    @method_takes(
        "fileDir", StringMeta("Directory to write HDF files into"), REQUIRED,
        "fileName", StringMeta("HDF file name"), REQUIRED,
        "acqID", StringMeta("Acquisition ID to configure for"), REQUIRED,
        "datasets", StringArrayMeta("Name(s) of dataset(s)"), REQUIRED,
        "dataType", ChoiceMeta(
            "Data type of dataset", ("uint8", "uint16", "uint32")), REQUIRED,
        "dimensions", NumberArrayMeta("int16", "Frame dimensions"), REQUIRED,
        "chunks", NumberArrayMeta("int16", "Frame chunk dimensions"), None,
        "compression", ChoiceMeta(
            "Compression type", ("LZ4", "BSLZ4")), None)
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        if params.chunks is not None:
            chunks = params.chunks.tolist()
        else:
            chunks = None
        if params.compression is not None:
            compression = self.COMPRESSION_TYPES[params.compression]
        else:
            compression = None

        for dataset in params.datasets:
            self.client.create_dataset(
                dataset, self.DATA_TYPES[params.dataType],
                params.dimensions.tolist(),
                chunks, compression)

        self.client.configure_file(params.fileDir, params.fileName,
                                   steps_to_do, params.acqID)

    @RunnableController.Abort
    @RunnableController.Reset
    def stop(self, context):
        self.client.stop()

    @RunnableController.PostRunReady
    @RunnableController.Seek
    @method_takes(
        "active_frame", NumberMeta(
            "int16", "Frame ID to apply rewind from"), REQUIRED)
    def seek(self, context, completed_steps, steps_to_do, part_info, params):
        new_frame_count = completed_steps + steps_to_do
        self.client.rewind(new_frame_count - self.done_when_reaches,
                           params.active_frame)
        self.done_when_reaches = new_frame_count
