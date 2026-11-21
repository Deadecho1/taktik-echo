"""The artifact gate must reject missing and stale code or native bytecode."""

import importlib.util
import io
import subprocess
import sys
import tarfile
import zipfile

import pytest
from unit.paths import CORE

SPEC = importlib.util.spec_from_file_location(
    "verify_browsing_distribution",
    CORE / "scripts/build/verify_browsing_distribution.py",
)
distribution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(distribution)


def archive(tmp_path, suffix, files):
    path = tmp_path / ("taktik_bot-1.9.9" + suffix)
    if suffix == ".whl":
        with zipfile.ZipFile(path, "w") as output:
            for name, data in files.items():
                output.writestr(name, data)
    else:
        with tarfile.open(path, "w:gz") as output:
            for name, data in files.items():
                member = tarfile.TarInfo("taktik_bot-1.9.9/" + name)
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
    return path


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
def test_distribution_matches_the_checkout(tmp_path, suffix):
    expected = distribution.browsing_files(CORE)
    path = archive(tmp_path, suffix, expected)
    assert distribution.verify_archive(path, expected) == len(expected)


@pytest.mark.parametrize("suffix", [".whl", ".tar.gz"])
@pytest.mark.parametrize("change", ["missing", "stale"])
@pytest.mark.parametrize(
    "name",
    [
        "taktik/core/shared/phone_interaction/native/hierarchy-reader.dex",
        "taktik/core/social_media/x/services/browsing/browser.py",
    ],
)
def test_missing_or_stale_runtime_files_fail_the_gate(tmp_path, suffix, change, name):
    expected = distribution.browsing_files(CORE)
    files = dict(expected)
    if change == "missing":
        del files[name]
    else:
        files[name] = b"outdated artifact"
    path = archive(tmp_path, suffix, files)
    with pytest.raises(ValueError, match=name):
        distribution.verify_archive(path, expected)


def test_cli_rejects_a_source_archive_missing_install_requirements(tmp_path):
    files = distribution.browsing_files(CORE)
    for name in ("setup.py", "README.md", "MANIFEST.in"):
        files[name] = (CORE / name).read_bytes()
    path = archive(tmp_path, ".tar.gz", files)
    result = subprocess.run(
        [
            sys.executable,
            str(CORE / "scripts/build/verify_browsing_distribution.py"),
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing requirements.txt" in result.stderr
