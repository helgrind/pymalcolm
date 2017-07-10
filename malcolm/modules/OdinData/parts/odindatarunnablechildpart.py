from malcolm.core import method_takes
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.modules.scanning.parts import RunnableChildPart


class OdinDataRunnableChildPart(RunnableChildPart):

    def update_part_configure_args(self, response, without=()):
        # Decorate validate and configure with the sum of its parts
        super(OdinDataRunnableChildPart, self).update_part_configure_args(
            response, without=without + ("fileName",))

    def _params_with_file_name(self, params):
        new_params = dict(fileName=self.name + ".h5")
        new_params.update(params)
        return new_params

    # Method will be filled in by update_configure_validate_args
    @RunnableController.Validate
    @method_takes()
    def validate(self, context, part_info, params):
        params = self._params_with_file_name(params)
        return super(OdinDataRunnableChildPart, self).validate(
            context, part_info, params)

    # Method will be filled in at update_configure_validate_args
    @RunnableController.Configure
    @method_takes()
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        child = context.block_view(self.params.mri)
        if "fileName" in child.configure.takes.elements:
            params = self._params_with_file_name(params)
        child.configure(**params)
