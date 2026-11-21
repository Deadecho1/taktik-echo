"""Build the native reader with a supplied JDK and Google R8 compiler."""

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--r8", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    native = root / "taktik/core/shared/phone_interaction/native"
    with tempfile.TemporaryDirectory(prefix="taktik-hierarchy-build-") as temporary:
        classes = Path(temporary)
        subprocess.run(
            [
                str(args.java_home / "bin/javac"),
                "--release",
                "8",
                "-Xlint:-options",
                "-d",
                str(classes),
                str(native / "HierarchyReader.java"),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(args.java_home / "bin/java"),
                "-cp",
                str(args.r8),
                "com.android.tools.r8.D8",
                "--min-api",
                "26",
                "--output",
                str(classes),
                *(str(p) for p in sorted(classes.rglob("*.class"))),
            ],
            check=True,
        )
        shutil.copyfile(classes / "classes.dex", native / "hierarchy-reader.dex")
    manifest = {
        "minimum_android_api": 26,
        "compiler_sha256": hashlib.sha256(args.r8.read_bytes()).hexdigest(),
        "files": {
            name: hashlib.sha256((native / name).read_bytes()).hexdigest()
            for name in ("HierarchyReader.java", "hierarchy-reader.dex")
        },
    }
    (native / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
