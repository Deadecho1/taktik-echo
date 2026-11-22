# Maintained X fixture representation

The migration starts at main `dfad5ddc1cbd2533543660548c1f1c1bcac1fe4e`, whose tree equals tested revision `2615fe66641d43031f6597c42f0a7127ea7fd152`.
The original inventory contains 580 XML cases and 2,196 X/evaluator scenario IDs.
Original files, byte hashes, scenario IDs, and capture provenance are retained in local migration diagnostics.
The maintained [input inventory](../../tests/unit/social_media/x/fixtures/inputs.sha256) freezes canonical expanded-input hashes for every case.
Normal CI needs only this checkout.

Use `xml_fixture("expansion/wrapped-source.xml")` for complete native XML and `screen_fixture(name)` to invoke the real reader at the captured size.
Both live in [x_fixtures.py](../../tests/unit/x_fixtures.py).
Full XML files remain ordinary native hierarchies.
A `.case` file replaces only the storage of the corresponding `.xml` case name.
An empty recipe is a direct alias; a nonempty recipe applies explicit attribute or subtree edits to a full XML base.
Bases cannot themselves be aliases or recipes.
The base path is relative to the X fixture directory and its SHA-256 checks stored bytes before any edits.
Every XPath must identify exactly one element in the untouched base.
Conflicting edits and edits inside a replaced subtree fail.
Every expansion starts from fresh input, without shared mutable trees or production recognition decisions.

For inspection from the repository root:

```bash
PYTHONPATH=tests:. python -m unit.x_fixtures expansion/wrapped-source.xml > /tmp/wrapped-source.xml
PYTHONPATH=tests:. python scripts/eval/compare_x_fixtures.py /path/to/original-fixtures
```

The comparison checks every native hierarchy and the complete real reader result against the frozen original input.
Canonical XML removes formatting indentation between elements only, retaining attribute values, semantic text, sibling order, and `xml:space` content.
The per-case inventory hashes expanded canonical XML, not stored recipe bytes or original private captures.
Base hashes protect stored XML bytes separately.
Family manifests identify canonical XML hashes explicitly when migrated; non-XML asset hashes continue to describe stored bytes.
Private capture paths and source hashes belong in local provenance records, not new maintained recipes.

The corrected assessment includes native `lxml.etree.parse` reads as well as Python file reads.
Its 59 unread and six integrity-only cases remain retained during this migration.
No behavioral scenario is removed on the basis of runtime-use evidence alone.
The two replay boundaries remain separate: Phone-operation doubles and raw Android transports beneath real Phone/TaktikDevice execution.
