"""Tests for the action protocol parser (app/protocol.py)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))

from app.protocol import FinalAction, ProtocolError, ToolAction, parse_action


class TestParseAction(unittest.TestCase):
    def test_plain_tool_json(self):
        action = parse_action('{"action": "tool", "tool": "read_file", "args": {"path": "a.txt"}}')
        self.assertIsInstance(action, ToolAction)
        self.assertEqual(action.tool, "read_file")
        self.assertEqual(action.args, {"path": "a.txt"})

    def test_fenced_json(self):
        action = parse_action('```json\n{"action": "final", "answer": "done"}\n```')
        self.assertIsInstance(action, FinalAction)
        self.assertEqual(action.answer, "done")

    def test_json_with_surrounding_prose(self):
        action = parse_action('Sure! {"action": "final", "answer": "ok"} hope that helps')
        self.assertIsInstance(action, FinalAction)

    def test_garbage_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_action("I will now read the file.")

    def test_unknown_action_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_action('{"action": "teleport"}')

    def test_tool_without_name_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_action('{"action": "tool", "args": {}}')

    def test_final_without_answer_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_action('{"action": "final"}')

    def test_non_object_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_action('["action", "tool"]')


if __name__ == "__main__":
    unittest.main()
