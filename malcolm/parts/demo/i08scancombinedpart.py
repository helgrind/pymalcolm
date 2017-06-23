from scanpointgenerator import LineGenerator, SpiralGenerator

from malcolm.core import method_takes
from malcolm.parts.builtin.runnablechildpart import RunnableChildPart
from malcolm.controllers.runnablecontroller import RunnableController


class I08ScanCombinedPart(RunnableChildPart):
    def _get_range(self, params, name="X"):
        search_name = "Sample%s" % name
        for d in params.generator.dimensions:
            if search_name in d.axes:
                index = d.axes.index(search_name)
                return d.lower[index], d.upper[index]
        current = self.child["positionT1%sC" % name].value
        return current, current

    # MethodMeta will be filled in by _update_configure_args
    @RunnableController.Configure
    @method_takes()
    def configure(self, task, completed_steps, steps_to_do, part_info, params):
        xstart, xstop = self._get_range(params, "X")
        ystart, ystop = self._get_range(params, "Y")
        if abs(xstart - xstop) > 0.04 or abs(ystart - ystop) > 0.04:
            # outside the range of the piezo, do a combined scan
            task.put(self.child["fineMode"], 0)
        else:
            # inside the range of piezo, just move fine
            task.put(self.child["fineMode"], 1)
            # move to corrected centre of range
            xp = (xstop + xstart) / 2.0
            yp = (ystop + ystart) / 2.0
            # YC=-4, XC=0, gives XF=0.03
            xp -= yp * 0.03 / -4.0
            # XC=-4, YC=0, gives YF=0.05
            yp -= xp * 0.05 / -4.0
            fs = task.put_async(self.child["positionT1XC"], xp)
            fs += task.put_async(self.child["positionT1YC"], yp)
            task.wait_all(fs)
        super(I08ScanCombinedPart, self).configure(
            task, completed_steps, steps_to_do, part_info, params)

