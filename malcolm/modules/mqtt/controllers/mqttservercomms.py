from paho.mqtt import client

from malcolm.modules.builtin.controllers.servercomms import ServerComms
from malcolm.core import Hook, method_also_takes, Process, Subscribe, Update, Put, Unsubscribe
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta, BooleanMeta


@method_also_takes(
    "host", StringMeta("Address of MQTT broker"), "localhost",
    "port", NumberMeta("int32", "Port number to connect to the broker on"), 1883,
    "keepalive", NumberMeta("int32", "Number of seconds between pings to broker if no traffic since"), 60,
    "block", StringMeta("Block name to monitor"), "",
    "attribute", StringMeta("Attribute of block to monitor"), "",
    "read_only", BooleanMeta("Should MQTT only read and not write?"), True)
class MQTTServerComms(ServerComms):
    """A class for communication between Malcolm and an MQTT broker"""
    _server = None
    _spawned = None
    _blockname = None
    _attributename = None
    _topic = None
    _blocking = False
    use_cothread = False

    def do_init(self):
        self.log.warn(self.params.read_only)
        super(MQTTServerComms, self).do_init()
        self._blockname = self.params.block
        self._attributename = self.params.attribute
        self._topic = str.join("", [self._blockname, "/", self._attributename])
        self.start_io_loop()

    def start_io_loop(self):
        if self._spawned is None:
            self._server = client.Client()
            self._server.connect(self.params.host, int(self.params.port), self.params.keepalive)
            # self._spawned = self.spawn(self._server.loop_start())
            self._subscribe(self.params.block, self.params.attribute)
            if not self.is_read_only():
                self.log.warn("$$$ Got to subs routine")
                self._server.on_message = self._mqtt_receive
                self._server.subscribe(self._topic)
            self._server.loop_start()

    def stop_io_loop(self):
        # if self._spawned:
        #    self._loop.add_callback(self._server.disconnect)
        #    self._spawned.wait(timeout=10)
        #    self._spawned = None
        self._server.disconnect()

    def do_disable(self):
        super(MQTTServerComms, self).do_disable()
        self.stop_io_loop()

    def do_reset(self):
        super(MQTTServerComms, self).do_reset()
        self.start_io_loop()

    def _subscribe(self, block, attribute):
        controller = self.process.get_controller(block)
        request = Subscribe(path=[block, attribute, "value"],
                            callback=self._on_response)
        controller.handle_request(request)

    def _on_response(self, response):
        # type: (Update) -> None
        if not self._blocking:
            new_value = response.value
            self._server.publish(self._topic, str(new_value))

    def _mqtt_receive(self, clnt, userdata, message):
        [block, attribute] = message.topic.split("/")
        self._disable_mqtt()
        controller = self.process.get_controller(block)
        request = Put(path=[block, attribute, "value"],
                      value=message.payload,
                      callback=self._enable_mqtt)
        controller.handle_request(request)

    def _enable_mqtt(self, *args):
        self._blocking = False

    def _disable_mqtt(self):
        self._blocking = True

    def is_read_only(self):
        return bool(self.params.read_only)
