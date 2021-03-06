from mock import Mock

from malcolm.testutil import ChildTestCase
from malcolm.modules.ADPandABlocks.blocks import pandablocks_runnable_block


class TestADPandABlocksBlocks(ChildTestCase):
    def test_pandablocks_runnable_block(self):
        self.create_child_block(
            pandablocks_runnable_block, Mock(),
            mriPrefix="mriPrefix", pvPrefix="pvPrefix", configDir="/tmp")
