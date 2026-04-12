from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from xmldiffstudio.diff_engine import DiffEngine


class DiffEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DiffEngine()

    def _compare_xml(self, left: str, right: str):
        with tempfile.TemporaryDirectory() as tmp:
            left_path = Path(tmp) / "left.xml"
            right_path = Path(tmp) / "right.xml"
            left_path.write_text(left, encoding="utf-8")
            right_path.write_text(right, encoding="utf-8")
            return self.engine.compare_paths(left_path, right_path)

    def _compare_json(self, left: str, right: str):
        with tempfile.TemporaryDirectory() as tmp:
            left_path = Path(tmp) / "left.json"
            right_path = Path(tmp) / "right.json"
            left_path.write_text(left, encoding="utf-8")
            right_path.write_text(right, encoding="utf-8")
            return self.engine.compare_paths(left_path, right_path)

    def test_xml_namespace_nodes_are_distinct(self) -> None:
        left = """<root xmlns:a="urn:a" xmlns:b="urn:b"><a:item>1</a:item><b:item>2</b:item></root>"""
        right = """<root xmlns:a="urn:a" xmlns:b="urn:b"><a:item>1</a:item><b:item>3</b:item></root>"""
        result = self._compare_xml(left, right)
        self.assertEqual(1, len(result.items))
        self.assertIn("contenido", result.items[0].path)
        self.assertEqual("cambio", result.items[0].change_type)

    def test_xml_mixed_content_detects_text_changes(self) -> None:
        left = "<root>Hola <b>mundo</b>!</root>"
        right = "<root>Hola <b>equipo</b>!</root>"
        result = self._compare_xml(left, right)
        self.assertEqual(1, len(result.items))
        self.assertIn("mundo", result.items[0].before)
        self.assertIn("equipo", result.items[0].after)

    def test_json_list_alignment_marks_insertions_cleanly(self) -> None:
        left = '{"items":[{"id":1},{"id":3}]}'
        right = '{"items":[{"id":1},{"id":2},{"id":3}]}'
        result = self._compare_json(left, right)
        self.assertEqual(1, len(result.items))
        self.assertEqual("agregado", result.items[0].change_type)
        self.assertIn("$.items[1]", result.items[0].path)

    def test_json_value_change(self) -> None:
        left = '{"user":{"name":"Ana","active":true}}'
        right = '{"user":{"name":"Ana","active":false}}'
        result = self._compare_json(left, right)
        self.assertEqual(1, len(result.items))
        self.assertEqual("$.user.active", result.items[0].path)


if __name__ == "__main__":
    unittest.main()
