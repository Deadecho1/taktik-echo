"""Check built archives contain the checkout's browsing code and native assets."""

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def browsing_files(root):
    root = Path(root)
    paths = set()
    for package in ("social_media/x", "shared/phone_interaction"):
        paths.update((root / "taktik/core" / package).rglob("*.py"))
    for name in ("browsing.py", "post_urls.py"):
        paths.add(root / "taktik/core/shared" / name)
    native = root / "taktik/core/shared/phone_interaction/native"
    manifest_path = native / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths.add(manifest_path)
    for name in ("HierarchyReader.java", "hierarchy-reader.dex"):
        path = native / name
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["files"].get(name):
            raise ValueError(f"Native source manifest mismatch: {path}")
        paths.add(path)
    for path in tuple(paths):
        parent = path.parent
        while parent != root:
            paths.add(parent / "__init__.py")
            parent = parent.parent
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}


def verify_archive(path, expected):
    path = Path(path)
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            members = [member for member in archive if member.isfile()]
            roots = {PurePosixPath(member.name).parts[0] for member in members}
            if len(roots) != 1:
                raise ValueError(f"{path.name}: expected one source distribution root")
            files = {
                PurePosixPath(
                    *PurePosixPath(member.name).parts[1:]
                ).as_posix(): archive.extractfile(member).read()
                for member in members
            }
    else:
        raise ValueError(f"Unsupported distribution: {path}")
    for name, data in sorted(expected.items()):
        if name not in files:
            raise ValueError(f"{path.name}: missing {name}")
        if files[name] != data:
            raise ValueError(f"{path.name}: checkout content differs for {name}")
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        root = Path(__file__).resolve().parents[2]
        expected = browsing_files(root)
        for path in args.archives:
            required = dict(expected)
            if path.name.endswith(".tar.gz"):
                for name in (
                    "setup.py",
                    "requirements.txt",
                    "README.md",
                    "MANIFEST.in",
                ):
                    required[name] = (root / name).read_bytes()
            count = verify_archive(path, required)
            print(f"{path.name}: verified {count} browsing source and asset files")
    except (
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as error:
        parser.exit(1, f"Distribution verification failed: {error}\n")


if __name__ == "__main__":
    main()
