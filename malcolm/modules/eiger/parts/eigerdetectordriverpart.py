from malcolm.modules.ADCore.parts import ExposureDetectorDriverPart


class EigerDetectorDriverPart(ExposureDetectorDriverPart):
    def is_hardware_triggered(self, child):
        return False
        return child.triggerMode.value != "Internal"
