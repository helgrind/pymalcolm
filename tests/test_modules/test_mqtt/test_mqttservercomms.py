import unittest

from malcolm.modules.mqtt.controllers import MQTTServerComms
from malcolm.core import Process, call_with_params


class TestMQTTServerComms(unittest.TestCase):

    def setUp(self):
        self.process = Process("proc")
        self.o = call_with_params(MQTTServerComms, self.process, (),
                                  mri="mri", block="block", attribute="attribute", topic_prefix="prefix")

    def test_init(self):
        assert self.o.mri == "mri"
	assert self.o.params.host == "localhost"
        assert self.o.params.port == 1883
        assert self.o.params.keepalive == 60
	assert self.o.params.block == "block"
	assert self.o.params.attribute == "attribute"
	assert self.o.params.topic_prefix == "prefix"
	assert self.o.params.read_only == True
