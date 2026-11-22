"""Complete native XML inputs, with checked, single-step fixture recipes.

Inspect a case with: PYTHONPATH=tests python -m unit.x_fixtures NAME
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from lxml import etree

FIXTURES = Path(__file__).parent / "social_media/x/fixtures"
SIZE = (1080, 2340)


class FixtureError(ValueError):
    """A fixture reference or recipe cannot be applied unambiguously."""


def canonical_xml(xml: str | bytes) -> bytes:
    """Ignore indentation between elements, retaining text and attribute values."""
    root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    for node in root.iter():
        if node.xpath("ancestor-or-self::*[@xml:space='preserve']"):
            continue
        if (node.text and node.text.strip()) or any(
            c.tail and c.tail.strip() for c in node
        ):
            continue
        if len(node) and node.text and not node.text.strip() and "\n" in node.text:
            node.text = None
        for child in node:
            if child.tail and not child.tail.strip() and "\n" in child.tail:
                child.tail = None
    return etree.tostring(root, method="c14n")


class FixtureStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, name: str | Path) -> Path:
        path = Path(name)
        if ".." in path.parts:
            raise FixtureError(f"Invalid fixture reference: {name}")
        path = (self.root / path).resolve()
        if not path.is_relative_to(self.root) or path.suffix != ".xml":
            raise FixtureError(f"Invalid fixture reference: {name}")
        return path

    def xml(self, name: str | Path) -> str:
        path = self._path(name)
        recipe = path.with_suffix(".case")
        if path.exists() and recipe.exists():
            raise FixtureError(f"Both full XML and recipe exist: {name}")
        if path.exists():
            return path.read_text(encoding="utf-8")
        if not recipe.exists():
            raise FixtureError(f"Missing fixture: {name}")
        try:
            return self._expand(recipe)
        except (ValueError, OSError, etree.LxmlError) as error:
            raise FixtureError(f"{name}: {error}") from error

    def _expand(self, path: Path) -> str:
        recipe = etree.fromstring(path.read_bytes())
        if recipe.tag != "fixture" or set(recipe.attrib) != {"base", "sha256"}:
            raise FixtureError("Expected fixture with base and sha256")
        self._wrapper_text(recipe)
        base = self._path(recipe.get("base"))
        if base.with_suffix(".case").exists():
            raise FixtureError(
                "Base must be full XML; derivation and alias chains are forbidden"
            )
        if not base.is_file():
            raise FixtureError(f"Missing base: {recipe.get('base')}")
        data = base.read_bytes()
        if hashlib.sha256(data).hexdigest() != recipe.get("sha256"):
            raise FixtureError(f"Base checksum mismatch: {recipe.get('base')}")
        root = etree.fromstring(data)
        edits = []
        touched = {}
        for edit in recipe:
            selector = edit.get("select")
            if not selector:
                raise FixtureError("Every edit needs a select XPath")
            matches = root.xpath(selector)
            if not isinstance(matches, list) or len(matches) != 1:
                raise FixtureError(f"Expected exactly one target: {selector}")
            target = matches[0]
            if not isinstance(target, etree._Element):
                raise FixtureError(f"Target must be an element: {selector}")
            self._validate_edit(edit, target)
            fields = (
                set(edit.attrib) - {"select"}
                if edit.tag == "set"
                else set(edit.get("names", "").split())
            )
            previous = touched.setdefault(target, set())
            if (
                previous & fields
                or "*" in previous
                or (edit.tag == "replace" and previous)
            ):
                raise FixtureError(f"Conflicting edits: {selector}")
            previous.update(fields if edit.tag != "replace" else {"*"})
            edits.append((edit, target))
        # Resolve against the original layout, so attribute changes cannot retarget later edits.
        for edit, target in edits:
            if any(
                other.tag == "replace" and parent in target.iterancestors()
                for other, parent in edits
            ):
                raise FixtureError("Edits overlap a replaced subtree")
            if edit.tag == "set":
                target.attrib.update(
                    {k: v for k, v in edit.attrib.items() if k != "select"}
                )
            elif edit.tag == "unset":
                for name in edit.get("names").split():
                    del target.attrib[name]
            else:
                replacement = copy.deepcopy(edit[0])
                replacement.tail = target.tail
                if target is root:
                    root = replacement
                else:
                    target.getparent().replace(target, replacement)
        return etree.tostring(root, encoding="unicode")

    @staticmethod
    def _wrapper_text(element):
        if (element.text and element.text.strip()) or any(
            child.tail and child.tail.strip() for child in element
        ):
            raise FixtureError(f"Unexpected text in {element.tag} wrapper")

    @staticmethod
    def _validate_edit(edit, target):
        FixtureStore._wrapper_text(edit)
        keys = set(edit.attrib)
        if edit.tag == "set" and not len(edit) and keys > {"select"}:
            return
        if edit.tag == "unset" and not len(edit) and keys == {"select", "names"}:
            names = edit.get("names").split()
            if (
                names
                and len(set(names)) == len(names)
                and all(n in target.attrib for n in names)
            ):
                return
        if edit.tag == "replace" and len(edit) == 1 and keys == {"select"}:
            return
        raise FixtureError(f"Invalid {edit.tag} edit for {edit.get('select')}")


def xml_fixture(name: str | Path) -> str:
    """Return a fresh XML string; names are relative to the X fixture directory."""
    path = Path(name)
    return FixtureStore(FIXTURES).xml(path if path.suffix else path.with_suffix(".xml"))


def screen_fixture(name: str | Path):
    from taktik.core.social_media.x.ui.screen import read_screen

    return read_screen(xml_fixture(name), SIZE)


def fixture_digest(path: str | Path) -> str:
    """XML hashes describe expanded inputs; other assets hash their stored bytes."""
    path = Path(path)
    data = (
        canonical_xml(xml_fixture(path)) if path.suffix == ".xml" else path.read_bytes()
    )
    return hashlib.sha256(data).hexdigest()


def fixture_manifest(path: Path) -> dict:
    """Check canonical inputs separately from stored-byte hashes of other assets."""
    manifest = json.loads(path.read_text())
    assert manifest["xml_hash"] == "canonical-xml-v1", path
    for entry in manifest.get("fixtures", manifest.get("cases", [])):
        assert fixture_digest(path.parent / entry["file"]) == entry["sha256"], entry[
            "file"
        ]
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Case name, including .xml and family directory")
    args = parser.parse_args()
    print(xml_fixture(args.name))


if __name__ == "__main__":
    main()
