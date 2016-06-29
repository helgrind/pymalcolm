import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
import setup_malcolm_paths

from collections import OrderedDict

import unittest
from mock import MagicMock, call, patch

# module imports
from malcolm.core.block import Block
from malcolm.core.attribute import Attribute
from malcolm.core.stringmeta import StringMeta
from malcolm.core.method import Method
from malcolm.core.serializable import Serializable


class TestBlock(unittest.TestCase):

    def test_init(self):
        b = Block("blockname")
        self.assertEqual(b.name, "blockname")
        self.assertEqual(list(b._methods), [])
        self.assertEqual("malcolm:core/Block:1.0", b.typeid)

    def test_add_method_registers(self):
        b = Block("blockname")
        b.on_changed = MagicMock(side_effect=b.on_changed)
        m = MagicMock()
        m.name = "mymethod"
        b.add_method(m)
        self.assertEqual(list(b._methods), ["mymethod"])
        self.assertFalse(m.called)
        b.on_changed.assert_called_with([[m.name], m.to_dict.return_value])
        m.return_value = 42
        self.assertEqual(b.mymethod(), 42)
        m.assert_called_once_with()

    def test_add_attribute(self):
        b = Block("blockname")
        b.on_changed = MagicMock(side_effect=b.on_changed)
        attr = MagicMock()
        attr.name = "attr"
        b.add_attribute(attr)
        attr.set_parent.assert_called_once_with(b)
        self.assertEqual({"attr":attr}, b._attributes)
        self.assertIs(attr, b.attr)
        b.on_changed.assert_called_with(
            [[attr.name], attr.to_dict.return_value])

    def test_lock_released(self):
        b = Block("blockname")
        acquire = MagicMock()
        release = MagicMock()
        lock_methods = MagicMock()
        lock_methods.attach_mock(acquire, "acquire")
        lock_methods.attach_mock(release, "release")
        def enter_side_effect(*args):
            acquire()
        def exit_side_effect(*args):
            release()
        b.lock = MagicMock()
        b.lock.__enter__.side_effect = enter_side_effect
        b.lock.__exit__.side_effect = exit_side_effect

        with b.lock:
            with b.lock_released():
                pass

        self.assertEquals(
            [call.acquire(), call.release(), call.acquire(), call.release()],
            lock_methods.method_calls)

class TestUpdates(unittest.TestCase):

    def test_simple_update(self):
        b = Block("b")
        m = MagicMock()
        m.name = "m"
        b.m = m
        change_dict = MagicMock()
        change = [["m", "sub_structure"], change_dict]
        b.update(change)

        m.update.assert_called_with([["sub_structure"], change_dict])

    def test_update_adds_attribute(self):
        b = Block("b")
        b.add_attribute = MagicMock(wrap=b.add_attribute)
        b.add_method = MagicMock(wrap=b.add_method)
        attr_meta = StringMeta("attr", "desc")
        attr = Attribute(attr_meta)
        change_dict = attr.to_dict()
        change = [["attr"], change_dict]

        b.update(change)

        added_attr = b.add_attribute.call_args[0][0]
        self.assertEquals(Attribute, type(added_attr))
        self.assertEquals(change_dict, added_attr.to_dict())
        b.add_method.assert_not_called()

    def test_update_adds_method(self):
        b = Block("b")
        b.add_attribute = MagicMock(wrap=b.add_attribute)
        b.add_method = MagicMock(wrap=b.add_method)
        method = Method("method", "desc")
        change_dict = method.to_dict()
        change = [["method"], change_dict]

        b.update(change)

        added_method = b.add_method.call_args[0][0]
        self.assertEquals(Method, type(added_method))
        self.assertEquals(change_dict, added_method.to_dict())
        b.add_attribute.assert_not_called()

    def test_update_raises_if_missing_path(self):
        b = Block("b")
        change = [["missing", "path"], MagicMock()]
        with self.assertRaises(
                ValueError, msg="Missing substructure at %s" % change[0][0]):
            b.update(change)

    @patch("malcolm.core.serializable.Serializable.from_dict")
    def test_update_raises_if_wrong_object(self, from_dict_mock):
        b = Block("b")
        change = [["path"], MagicMock()]
        with self.assertRaises(
                ValueError, msg="Change %s deserializaed to unknown object %s"
                % (change, from_dict_mock.return_value)):
            b.update(change)

class TestToDict(unittest.TestCase):

    def test_returns_dict(self):
        method_dict = OrderedDict(takes=OrderedDict(one=OrderedDict()),
                                  returns=OrderedDict(one=OrderedDict()),
                                  defaults=OrderedDict())

        m1 = MagicMock()
        m1.name = "method_one"
        m1.to_dict.return_value = method_dict

        m2 = MagicMock()
        m2.name = "method_two"
        m2.to_dict.return_value = method_dict

        a1 = MagicMock()
        a1.name = "attr_one"
        a1dict = OrderedDict(value="test", meta=MagicMock())
        a1.to_dict.return_value = a1dict

        a2 = MagicMock()
        a2.name = "attr_two"
        a2dict = OrderedDict(value="value", meta=MagicMock())
        a2.to_dict.return_value = a2dict

        block = Block("Test")
        block.add_method(m1)
        block.add_method(m2)
        block.add_attribute(a1)
        block.add_attribute(a2)

        m1.reset_mock()
        m2.reset_mock()
        a1.reset_mock()
        a2.reset_mock()

        expected_dict = OrderedDict()
        expected_dict['attr_one'] = a1dict
        expected_dict['attr_two'] = a2dict
        expected_dict['method_one'] = method_dict
        expected_dict['method_two'] = method_dict
        expected_dict['typeid'] = "malcolm:core/Block:1.0"

        response = block.to_dict()

        m1.to_dict.assert_called_once_with()
        m2.to_dict.assert_called_once_with()
        self.assertEqual(expected_dict, response)


class TestHandleRequest(unittest.TestCase):

    def setUp(self):
        self.block = Block("TestBlock")
        self.block.parent = MagicMock()
        self.method = MagicMock()
        self.method.name = "get_things"
        self.attribute = MagicMock()
        self.attribute.name = "test_attribute"
        self.response = MagicMock()
        self.block.add_method(self.method)
        self.block.add_attribute(self.attribute)

    def test_given_request_then_pass_to_correct_method(self):
        request = MagicMock()
        request.type_ = "Post"
        request.endpoint = ["TestBlock", "device", "get_things"]

        self.block.handle_request(request)

        self.method.get_response.assert_called_once_with(request)
        response = self.method.get_response.return_value
        self.block.parent.block_respond.assert_called_once_with(
            response, request.response_queue)

    def test_given_put_then_update_attribute(self):
        put_value = MagicMock()
        request = MagicMock()
        request.type_ = "Put"
        request.endpoint = ["TestBlock", "test_attribute"]
        request.value = put_value

        self.block.handle_request(request)

        self.attribute.put.assert_called_once_with(put_value)
        self.attribute.set_value.assert_called_once_with(put_value)
        response = self.block.parent.block_respond.call_args[0][0]
        self.assertEqual("Return", response.type_)
        self.assertIsNone(response.value)
        response_queue = self.block.parent.block_respond.call_args[0][1]
        self.assertEqual(request.response_queue, response_queue)

    def test_invalid_request_fails(self):
        request = MagicMock()
        request.type_ = "Get"

        self.assertRaises(AssertionError, self.block.handle_request, request)

if __name__ == "__main__":
    unittest.main(verbosity=2)
