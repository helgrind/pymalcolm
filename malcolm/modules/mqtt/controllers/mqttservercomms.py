from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.web import Application

from paho.mqtt import client

from malcolm.modules.builtin.controllers.servercomms import ServerComms
from malcolm.core import Hook, method_also_takes, Process
from malcolm.modules.builtin.vmetas import StringMeta, NumberMeta
from malcolm.modules.web.infos import HandlerInfo


@method_also_takes(
    "host", StringMeta("Address of MQTT broker"), "localhost",
    "port", NumberMeta("int32", "Port number to connect to the broker on"), 1883,
    "keepalive", NumberMeta("int32", "Number of seconds between pings to broker if no traffic since"), 60)
class MQTTServerComms(ServerComms):
    """A class for communication between Malcolm and an MQTT broker"""
    _server = None
    _spawned = None
    use_cothread = False

    ReportHandlers = Hook()
    """Called at init() to get all the handlers that should make the application

    Args:
        context (Context): The context that should be used to perform operations
            on child blocks
        loop (IOLoop): The IO loop that the server is running under

    Returns:
        [`HandlerInfo`] - any handlers and their regexps that need to form part
            of the tornado Application
    """

    Publish = Hook()
    """Called when a new block is added

    Args:
        context (Context): The context that should be used to perform operations
            on child blocks
        published (list): [mri] list of published Controller mris
    """

    def do_init(self):
        super(MQTTServerComms, self).do_init()
        self.start_io_loop()

    def start_io_loop(self):
        if self._spawned is None:
            self._server = client.Client()
            self._server.connect(self.params.host, self.params.port, self.params.keepalive)
            self._spawned = self.spawn(self._server.loop_forever())

    def stop_io_loop(self):
        if self._spawned:
            self._loop.add_callback(self._server.disconnect)
            self._spawned.wait(timeout=10)
            self._spawned = None

    def do_disable(self):
        super(MQTTServerComms, self).do_disable()
        self.stop_io_loop()

    def do_reset(self):
        super(MQTTServerComms, self).do_reset()
        self.start_io_loop()

    @Process.Publish
    def publish(self, published):
        if self._spawned:
            self.run_hook(self.Publish, self.create_part_contexts(), published)
