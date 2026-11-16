"""ADB discovery and read-only diagnostics, centralized with device access."""

import subprocess


def _adb_read(adb, *arguments):
    result = subprocess.run(
        [str(adb), *arguments], capture_output=True, text=True, timeout=20, check=False
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "ADB read failed."
        )
    return result.stdout


def device_list(adb):
    output = _adb_read(adb, "devices", "-l")
    return output, {
        fields[0]: fields[1]
        for line in output.splitlines()[1:]
        if len(fields := line.split()) >= 2
    }


def device_details(adb, serial, package):
    properties = {
        name: _adb_read(adb, "-s", serial, "shell", "getprop", name).strip()
        for name in (
            "ro.product.model",
            "ro.build.version.release",
            "ro.product.cpu.abi",
        )
    }
    installed = _adb_read(adb, "-s", serial, "shell", "dumpsys", "package", package)
    version = next(
        (line.strip() for line in installed.splitlines() if "versionName=" in line),
        None,
    )
    return properties, version
