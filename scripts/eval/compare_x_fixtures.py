"""Compare maintained X inputs and real parser outcomes with a migration baseline.

PYTHONPATH=tests:. python scripts/eval/compare_x_fixtures.py /path/to/original-fixtures
Normal CI uses inputs.sha256 and does not need the migration baseline.
"""

import argparse
from pathlib import Path

from unit.x_fixtures import FIXTURES, SIZE, canonical_xml, xml_fixture

from taktik.core.social_media.x.ui.screen import read_screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    names = [
        line.split()[1]
        for line in (FIXTURES / "inputs.sha256").read_text().splitlines()
    ]
    assert set(names) == {
        str(p.relative_to(args.baseline)) for p in args.baseline.rglob("*.xml")
    }
    for name in names:
        before = (args.baseline / name).read_text()
        after = xml_fixture(name)
        assert canonical_xml(before) == canonical_xml(after), (
            f"Native hierarchy changed: {name}"
        )
        assert read_screen(before, SIZE) == read_screen(after, SIZE), (
            f"Parser outcome changed: {name}"
        )
    print(f"{len(names)} native hierarchies and real parser outcomes match")


if __name__ == "__main__":
    main()
