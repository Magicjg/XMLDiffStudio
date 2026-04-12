from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from lxml import etree


def split_qname(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, local_name = tag[1:].split("}", 1)
        return namespace, local_name
    return None, tag


@dataclass(frozen=True)
class DiffItem:
    change_type: str
    path: str
    before: str
    after: str


@dataclass(frozen=True)
class DiffResult:
    items: list[DiffItem]

    @property
    def counts(self) -> dict[str, int]:
        counts = {"cambio": 0, "agregado": 0, "eliminado": 0, "tipo": 0}
        for item in self.items:
            counts[item.change_type] = counts.get(item.change_type, 0) + 1
        counts["total"] = len(self.items)
        return counts


class DiffEngine:
    def load_file(self, path: Path) -> Any:
        suffix = path.suffix.lower()
        if suffix == ".xml":
            return self._load_xml_as_data(path)
        if suffix == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        raise ValueError("Solo se soportan XML y JSON.")

    def compare_paths(self, left_path: Path, right_path: Path) -> DiffResult:
        left_data = self.load_file(left_path)
        right_data = self.load_file(right_path)
        items: list[DiffItem] = []
        self._compare_nodes(left_data, right_data, "$", items)
        return DiffResult(items)

    def _load_xml_as_data(self, path: Path) -> Any:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=False, recover=False)
        tree = etree.parse(str(path), parser=parser)
        return self._element_to_data(tree.getroot())

    def _element_to_data(self, element: etree._Element) -> dict[str, Any]:
        namespace, local_name = split_qname(element.tag)
        node: dict[str, Any] = {
            "__kind__": "xml_element",
            "__tag__": local_name,
            "__ns__": namespace or "",
            "__attrs__": self._normalize_attrs(element.attrib),
            "__children__": [],
        }

        if element.text and element.text.strip():
            node["__children__"].append(self._text_node(element.text))

        for child in list(element):
            node["__children__"].append(self._element_to_data(child))
            if child.tail and child.tail.strip():
                node["__children__"].append(self._text_node(child.tail))

        return node

    def _normalize_attrs(self, attrib: Any) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for raw_key, value in sorted(attrib.items(), key=lambda item: item[0]):
            namespace, local_name = split_qname(raw_key)
            display_name = f"{{{namespace}}}{local_name}" if namespace else local_name
            normalized[display_name] = value
        return normalized

    def _text_node(self, value: str) -> dict[str, str]:
        return {"__kind__": "xml_text", "__value__": value.strip()}

    def _compare_nodes(self, left: Any, right: Any, path: str, items: list[DiffItem]) -> None:
        if type(left) != type(right):
            items.append(DiffItem("tipo", path, self._preview(left), self._preview(right)))
            return

        if isinstance(left, dict):
            self._compare_dicts(left, right, path, items)
            return

        if isinstance(left, list):
            self._compare_lists(left, right, path, items)
            return

        if left != right:
            items.append(DiffItem("cambio", path, self._preview(left), self._preview(right)))

    def _compare_dicts(self, left: dict[str, Any], right: dict[str, Any], path: str, items: list[DiffItem]) -> None:
        left_keys = set(left.keys())
        right_keys = set(right.keys())
        for key in sorted(left_keys - right_keys):
            items.append(DiffItem("eliminado", self._join_path(path, key), self._preview(left[key]), ""))
        for key in sorted(right_keys - left_keys):
            items.append(DiffItem("agregado", self._join_path(path, key), "", self._preview(right[key])))
        for key in sorted(left_keys & right_keys):
            next_path = f"{path}.contenido" if key == "__children__" else self._join_path(path, key)
            self._compare_nodes(left[key], right[key], next_path, items)

    def _compare_lists(self, left: list[Any], right: list[Any], path: str, items: list[DiffItem]) -> None:
        left_signatures = [self._signature(value) for value in left]
        right_signatures = [self._signature(value) for value in right]
        matcher = SequenceMatcher(a=left_signatures, b=right_signatures, autojunk=False)

        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                for left_index, right_index in zip(range(left_start, left_end), range(right_start, right_end)):
                    self._compare_nodes(left[left_index], right[right_index], self._index_path(path, right_index), items)
                continue

            if tag == "replace":
                overlap = min(left_end - left_start, right_end - right_start)
                for offset in range(overlap):
                    left_index = left_start + offset
                    right_index = right_start + offset
                    self._compare_nodes(left[left_index], right[right_index], self._index_path(path, right_index), items)
                for left_index in range(left_start + overlap, left_end):
                    items.append(DiffItem("eliminado", self._index_path(path, left_index), self._preview(left[left_index]), ""))
                for right_index in range(right_start + overlap, right_end):
                    items.append(DiffItem("agregado", self._index_path(path, right_index), "", self._preview(right[right_index])))
                continue

            if tag == "delete":
                for left_index in range(left_start, left_end):
                    items.append(DiffItem("eliminado", self._index_path(path, left_index), self._preview(left[left_index]), ""))
                continue

            if tag == "insert":
                for right_index in range(right_start, right_end):
                    items.append(DiffItem("agregado", self._index_path(path, right_index), "", self._preview(right[right_index])))

    def _join_path(self, path: str, key: str) -> str:
        return f"{path}.{key}"

    def _index_path(self, path: str, index: int) -> str:
        return f"{path}[{index}]"

    def _signature(self, value: Any) -> str:
        if isinstance(value, dict):
            kind = value.get("__kind__")
            if kind == "xml_element":
                parts = [
                    "xml",
                    value.get("__ns__", ""),
                    value.get("__tag__", ""),
                    json.dumps(value.get("__attrs__", {}), sort_keys=True, ensure_ascii=False),
                ]
                parts.extend(self._signature(child) for child in value.get("__children__", [])[:3])
                return "|".join(parts)
        return json.dumps(value, sort_keys=True, ensure_ascii=False)

    def _preview(self, value: Any) -> str:
        if isinstance(value, dict):
            kind = value.get("__kind__")
            if kind == "xml_element":
                namespace = value.get("__ns__", "")
                tag = value.get("__tag__", "")
                attrs = value.get("__attrs__", {})
                attrs_text = ""
                if attrs:
                    attrs_text = " " + " ".join(f'{key}="{val}"' for key, val in attrs.items())
                name = f"{{{namespace}}}{tag}" if namespace else tag
                text = f"<{name}{attrs_text}>"
            elif kind == "xml_text":
                text = value.get("__value__", "")
            else:
                text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        elif isinstance(value, list):
            text = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        return text if len(text) <= 140 else text[:137] + "..."
