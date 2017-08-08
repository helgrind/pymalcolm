from collections import namedtuple, OrderedDict
import logging
import struct

# Create a module level logger
log = logging.getLogger(__name__)


# States
WAIT_HEADER_START = 0
WAIT_HEADER_END = 1
WAIT_DATA_START = 2
RECV_DATA = 3
DATA_END = 4


BlockData = namedtuple("BlockData", "number,description,fields")
FieldData = namedtuple("FieldData",
                       "field_type,field_subtype,description,labels")


class SocketReader(object):
    """Non threadsafe socket reader"""
    def __init__(self, socket, hostname, port):
        self._socket = socket
        self._socket.settimeout(1.0)
        self._socket.connect((hostname, port))
        self._buf = ""

    def shutdown(self):
        import socket
        self._socket.shutdown(socket.SHUT_RDWR)

    def close(self):
        self._socket.close()

    def send(self, message):
        self._socket.send(message)

    def _recv_more_data(self):
        rx = None
        while not rx:
            import socket
            try:
                rx = self._socket.recv(4096)
            except socket.error:
                rx = None
            else:
                log.debug("Received %d bytes: %r", len(rx), rx)
        self._buf += rx

    def recv_line(self):
        while "\n" not in self._buf:
            self._recv_more_data()
        line, self._buf = self._buf.split("\n", 1)
        return line

    def recv_bytes(self, size):
        while len(self._buf) < size:
            self._recv_more_data()
        bytes, self._buf = self._buf[:size], self._buf[size:]
        return bytes


class PandABlocksClient(object):
    # Sentinel that tells the send_loop and recv_loop to stop
    STOP = object()
    
    def __init__(self, hostname="localhost", port=8888, queue_cls=None,
                 dataport=8889):
        if queue_cls is None:
            try:
                # Python 2
                from Queue import Queue as queue_cls
            except ImportError:
                # Python 3
                from queue import Queue as queue_cls
        self.queue_cls = queue_cls
        self.hostname = hostname
        self.port = port
        self.dataport = dataport
        # Completed lines for a response in progress
        self._completed_response_lines = []
        # True if the current response is multiline
        self._is_multiline = None
        # True when we have been started
        self.started = False
        # Filled in on start
        self._reader = None
        self._send_spawned = None
        self._send_queue = None
        self._recv_spawned = None
        self._datareader = None
        self._data_spawned = None
        self._response_queues = None
        self._thread_pool = None

    def start(self, spawn=None, socket_cls=None):
        if spawn is None:
            from multiprocessing.pool import ThreadPool
            self._thread_pool = ThreadPool(3)
            spawn = self._thread_pool.apply_async
        if socket_cls is None:
            from socket import socket as socket_cls
        assert not self.started, "Send and recv threads already started"
        # Holds (message, response_queue) to send next
        self._send_queue = self.queue_cls()
        # Holds response_queue to send next
        self._response_queues = self.queue_cls()
        self._reader = SocketReader(socket_cls(), self.hostname, self.port)
        self._send_spawned = spawn(self._send_loop)
        self._recv_spawned = spawn(self._recv_loop)
        # If asked to do dataport
        if self.dataport:
            self._datareader = SocketReader(
                socket_cls(), self.hostname, self.dataport)
            self._data_spawned = spawn(self._data_loop)
        self.started = True
        
    def stop(self):
        assert self.started, "Send and recv threads not started"
        self._send_queue.put((self.STOP, None))    
        self._send_spawned.wait()
        self._reader.shutdown()
        self._recv_spawned.wait()
        self._reader.close()
        self._reader = None
        if self.dataport:
            self._datareader.shutdown()
            self._data_spawned.wait()
            self._datareader.close()
            self._datareader = None
        self.started = False
        if self._thread_pool is not None:
            self._thread_pool.close()
            self._thread_pool.join()
            self._thread_pool = None
        
    def send(self, message):
        response_queue = self.queue_cls()
        self._send_queue.put((message, response_queue))
        return response_queue

    def recv(self, response_queue, timeout=10.0):
        response = response_queue.get(timeout=timeout)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    def send_recv(self, message, timeout=10.0):
        """Send a message to a PandABox and wait for the response

        Args:
            message (str): The message to send
            timeout (float): How long to wait before raising queue.Empty

        Returns:
            str: The response
        """
        response_queue = self.send(message)
        response = self.recv(response_queue, timeout)
        return response

    def _send_loop(self):
        """Service self._send_queue, sending requests to server"""
        while True:
            message, response_queue = self._send_queue.get()
            if message is self.STOP:
                break
            try:
                self._response_queues.put(response_queue)
                self._reader.send(message)
            except Exception:  # pylint:disable=broad-except
                log.exception("Exception sending message %s", message)

    def _respond(self, resp):
        """Respond to the person waiting"""
        response_queue = self._response_queues.get(timeout=0.1)
        response_queue.put(resp)
        self._completed_response_lines = []
        self._is_multiline = None

    def _recv_loop(self):
        """Service socket recv, returning responses to the correct queue"""
        self._completed_response_lines = []
        self._is_multiline = None
        while True:
            try:
                line = self._reader.recv_line()
                if self._is_multiline is None:
                    self._is_multiline = line.startswith("!") or line == "."
                if line.startswith("ERR"):
                    self._respond(ValueError(line))
                elif self._is_multiline:
                    if line == ".":
                        self._respond(self._completed_response_lines)
                    else:
                        assert line[0] == "!", \
                            "Multiline response {} doesn't start with !" \
                                .format(repr(line))
                        self._completed_response_lines.append(line[1:])
                else:
                    self._respond(line)
            except Exception:
                log.exception("Exception receiving message")
                raise

    def _data_loop(self):
        """Service data socket, throwing away frames for now"""
        state = WAIT_HEADER_START
        header = ""
        self._datareader.send("XML FRAMED SCALED\n")
        while True:
            try:
                log.debug("State: %d", state)
                if state == WAIT_HEADER_START:
                    line = self._datareader.recv_line()
                    if line == "<header>":
                        header += line + "\n"
                        state = WAIT_HEADER_END
                elif state == WAIT_HEADER_END:
                    line = self._datareader.recv_line()
                    header += line + "\n"
                    if line == "</header>":
                        log.debug("Got header:\n%s", header)
                        # Eat the extra newline
                        line = self._datareader.recv_line()
                        assert line == "", "Expected \\n, got %r" % line
                        state = WAIT_DATA_START
                elif state == WAIT_DATA_START:
                    bytes = self._datareader.recv_bytes(4)
                    if bytes == "BIN ":
                        state = RECV_DATA
                    elif bytes == "END ":
                        state = DATA_END
                    else:
                        raise ValueError("Bad data %r" % bytes)
                elif state == RECV_DATA:
                    bytes = self._datareader.recv_bytes(4)
                    # Read message length as uint32 LE
                    length = struct.unpack("<I", bytes)[0]
                    packet = self._datareader.recv_bytes(length - 8)
                    log.debug("Got packet length %s", length)
                    state = WAIT_DATA_START
                elif state == DATA_END:
                    # Read out why we finished
                    line = self._datareader.recv_line()
                    log.debug("Data completed: %r", line)
                    header = ""
                    state = WAIT_HEADER_START
            except Exception:
                log.exception("Exception receiving message")
                raise

    def _get_block_numbers(self):
        block_numbers = OrderedDict()
        for line in self.send_recv("*BLOCKS?\n"):
            block_name, number = line.split()
            block_numbers[block_name] = int(number)
        return block_numbers

    def parameterized_send(self, request, parameter_list):
        """Send batched requests for a list of parameters

        Args:
            request (str): Request to send, like "%s.*?\n"
            parameter_list (list): parameters to format with, like
                ["TTLIN", "TTLOUT"]

        Returns:
            dict: {parameter: response_queue}
        """
        response_queues = OrderedDict()
        for parameter in parameter_list:
            response_queues[parameter] = self.send(request % parameter)
        return response_queues

    def get_blocks_data(self):
        blocks = OrderedDict()

        # Get details about number of blocks
        block_numbers = self._get_block_numbers()
        block_names = list(block_numbers)

        # TODO: goes in server
        block_names = [n for n in block_names if n != "POSITIONS"]

        # Queue up info about each block
        desc_queues = self.parameterized_send("*DESC.%s?\n", block_names)
        field_queues = self.parameterized_send("%s.*?\n", block_names)

        # Create BlockData for each block
        for block_name in block_names:
            number = block_numbers[block_name]
            description = self.recv(desc_queues[block_name])[4:]
            fields = OrderedDict()
            blocks[block_name] = BlockData(number, description, fields)

            # Parse the field list
            unsorted_fields = {}
            for line in self.recv(field_queues[block_name]):
                split = line.split()
                assert len(split) in (3, 4), \
                    "Expected field_data to have len 3 or 4, got {}"\
                    .format(len(split))
                if len(split) == 3:
                    split.append("")
                field_name, index, field_type, field_subtype = split
                # TODO: goes in server
                if block_name == "BITS" and field_name in ("ONE", "ZERO"):
                    continue
                # TODO: goes in server
                if field_subtype == "position":
                    if block_name.startswith("PCOMP") and field_name in (
                            "STEP", "WIDTH"):
                        field_subtype = "relative_pos"
                    else:
                        field_subtype = "pos"

                unsorted_fields[field_name] = (
                    int(index), field_type, field_subtype)

            # Sort the field list
            def get_field_index(field_name):
                return unsorted_fields[field_name][0]

            field_names = sorted(unsorted_fields, key=get_field_index)

            # Request description for each field
            field_desc_queues = self.parameterized_send(
                "*DESC.%s.%%s?\n" % block_name, field_names)

            # Request enum labels for fields that are enums
            enum_fields = []
            for field_name in field_names:
                _, field_type, field_subtype = unsorted_fields[field_name]
                if field_type in ("bit_mux", "pos_mux") or field_subtype == \
                        "enum":
                    enum_fields.append(field_name)
                elif field_type in ("pos_out", "ext_out"):
                    enum_fields.append(field_name + ".CAPTURE")
            enum_queues = self.parameterized_send(
                "*ENUMS.%s.%%s?\n" % block_name, enum_fields)

            # Get desc and enum data for each field
            for field_name in field_names:
                _, field_type, field_subtype = unsorted_fields[field_name]
                if field_name in enum_queues:
                    labels = self.recv(enum_queues[field_name])
                elif field_name + ".CAPTURE" in enum_queues:
                    labels = self.recv(enum_queues[field_name + ".CAPTURE"])
                else:
                    labels = []
                # TODO: goes in server
                for i, label in enumerate(labels):
                    if label in ("POSITIONS.ZERO", "BITS.ZERO"):
                        labels[i] = "ZERO"
                    elif label == "BITS.ONE":
                        labels[i] = "ONE"
                description = self.recv(field_desc_queues[field_name])[4:]
                fields[field_name] = FieldData(
                    field_type, field_subtype, description, labels)

        return blocks

    def get_changes(self):
        changes = OrderedDict()
        table_queues = {}
        for line in self.send_recv("*CHANGES?\n"):
            if line.endswith("(error)"):
                field = line.split(" ", 1)[0]
                val = Exception
            elif "<" in line:
                # table
                field = line.rstrip("<")
                val = None
                table_queues[field] = self.send("%s?\n" % field)
            elif "=" in line:
                field, val = line.split("=", 1)
            else:
                log.warning("Can't parse line %r of changes", line)
                continue
            # TODO: Goes in server
            if val in ("POSITIONS.ZERO", "BITS.ZERO"):
                val = "ZERO"
            elif val == "BITS.ONE":
                val = "ONE"
            changes[field] = val
        for field, q in table_queues.items():
            changes[field] = self.recv(q)
        return changes

    def get_table_fields(self, block, field):
        fields = OrderedDict()
        for line in self.send_recv("%s.%s.FIELDS?\n" % (block, field)):
            bits_str, name = line.split(" ", 1)
            name = name.strip()
            bits = tuple(int(x) for x in bits_str.split(":"))
            fields[name] = bits
        return fields

    def get_field(self, block, field):
        try:
            resp = self.send_recv("%s.%s?\n" % (block, field))
        except ValueError as e:
            raise ValueError("Error getting %s.%s: %s" % (
                block, field, e))
        else:
            assert resp.startswith("OK ="), "Expected 'OK =val', got %r" % resp
            value = resp[4:]
            return value

    def set_field(self, block, field, value):
        try:
            resp = self.send_recv("%s.%s=%s\n" % (block, field, value))
        except ValueError as e:
            raise ValueError("Error setting %s.%s to %r: %s" % (
                block, field, value, e))
        else:
            assert resp == "OK", "Expected OK, got %r" % resp

    def set_table(self, block, field, int_values):
        lines = ["%s.%s<\n" % (block, field)]
        lines += ["%s\n" % int_value for int_value in int_values]
        lines += ["\n"]
        resp = self.send_recv("".join(lines))
        assert resp == "OK", "Expected OK, got %r" % resp

if __name__ == "__main__":
    import logging
    logging.basicConfig(filename='panda.log', level=logging.DEBUG)
    client = PandABlocksClient("172.23.252.201")
    client.start()
    raw_input()
