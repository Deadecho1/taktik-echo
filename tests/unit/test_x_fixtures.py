"""Fixture recipes are deterministic input data, independent of X recognition."""

import hashlib

import pytest
from lxml import etree

from unit.x_fixtures import (
    FIXTURES,
    FixtureError,
    FixtureStore,
    canonical_xml,
    fixture_digest,
)


@pytest.fixture
def store(tmp_path):
    (tmp_path / "base.xml").write_text(
        '<root><item name="first"/><item name="last"/></root>'
    )
    return FixtureStore(tmp_path)


def recipe(store, edits="", *, base="base.xml", digest=None, name="variant.case"):
    if digest is None:
        digest = hashlib.sha256((store.root / "base.xml").read_bytes()).hexdigest()
    (store.root / name).write_text(
        f'<fixture base="{base}" sha256="{digest}">{edits}</fixture>'
    )


def test_attributes_subtrees_and_sibling_order(store):
    recipe(
        store,
        '<set select="//item[@name=\'first\']" selected="true"/>'
        '<unset select="//item[@name=\'first\']" names="name"/>'
        '<replace select="//item[@name=\'last\']"><group><child value="  text  "/></group></replace>',
    )
    root = etree.fromstring(store.xml("variant.xml"))
    assert [n.tag for n in root] == ["item", "group"]
    assert dict(root[0].attrib) == {"selected": "true"}
    assert root[1][0].get("value") == "  text  "


@pytest.mark.parametrize("base", ["missing.xml", "../base.xml", "/outside.xml"])
def test_invalid_base_reference(store, base):
    recipe(store, base=base)
    with pytest.raises(FixtureError, match="Missing base|Invalid fixture reference"):
        store.xml("variant.xml")


@pytest.mark.parametrize(
    "select", ["//missing", "//item", "count(//item)", "//item/@name"]
)
def test_edit_requires_exactly_one_element(store, select):
    recipe(store, f'<set select="{select}" selected="true"/>')
    with pytest.raises(FixtureError, match="exactly one target|must be an element"):
        store.xml("variant.xml")


@pytest.mark.parametrize(
    "edit",
    [
        '<set select="/root"/>',
        '<unset select="/root" names="missing"/>',
        '<replace select="/root"/>',
        '<remove select="/root"/>',
        '<set selected="true"/>',
        '<set select="[" selected="true"/>',
        '<set select="/root" a="1">ignored text</set>',
        '<replace select="/root"><new/>ignored tail</replace>',
        "ignored recipe text",
    ],
)
def test_invalid_edit(store, edit):
    recipe(store, edit)
    with pytest.raises(FixtureError):
        store.xml("variant.xml")


def test_stale_base_checksum(store):
    recipe(store)
    (store.root / "base.xml").write_text("<changed/>")
    with pytest.raises(FixtureError, match="checksum mismatch"):
        store.xml("variant.xml")


@pytest.mark.parametrize("base", ["variant.xml", "alias.xml"])
def test_alias_and_derivation_chains_are_rejected(store, base):
    recipe(store)
    recipe(store, base=base, name="alias.case")
    with pytest.raises(FixtureError, match="chains are forbidden"):
        store.xml("alias.xml")


def test_isolation_and_direct_alias(store):
    recipe(store)
    first = etree.fromstring(store.xml("variant.xml"))
    first.clear()
    assert canonical_xml(store.xml("variant.xml")) == canonical_xml(
        store.xml("base.xml")
    )


def test_overlapping_subtree_edits_are_rejected(store):
    recipe(
        store,
        '<replace select="/root"><new/></replace><set select="//item[@name=\'first\']" x="1"/>',
    )
    with pytest.raises(FixtureError, match="overlap"):
        store.xml("variant.xml")


def test_only_formatting_indentation_is_normalized():
    assert canonical_xml('<root>\n  <item value="  x  "> </item>\n</root>') == (
        b'<root><item value="  x  "> </item></root>'
    )
    assert b"\n " in canonical_xml('<root xml:space="preserve">\n <item/>\n</root>')
    assert b"\n " in canonical_xml("<root>text<item/>\n </root>")


def test_conflicting_edits_are_rejected(store):
    recipe(store, '<set select="/root" x="1"/><set select="/root" x="2"/>')
    with pytest.raises(FixtureError, match="Conflicting edits"):
        store.xml("variant.xml")


def test_inventory_covers_every_stored_case():
    names = {
        line.split()[1]
        for line in (FIXTURES / "inputs.sha256").read_text().splitlines()
    }
    paths = list(FIXTURES.rglob("*.xml")) + list(FIXTURES.rglob("*.case"))
    assert names == {str(p.relative_to(FIXTURES).with_suffix(".xml")) for p in paths}


@pytest.mark.parametrize(
    "digest,name",
    [line.split() for line in (FIXTURES / "inputs.sha256").read_text().splitlines()],
    ids=lambda value: value if value.endswith(".xml") else "input",
)
def test_expanded_fixture_integrity(digest, name):
    assert fixture_digest(name) == digest
