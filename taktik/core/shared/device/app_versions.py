"""Refuse app automation unless the actual package reports an exact pinned build."""

from taktik.core.shared.device import app_inspection, apps
from taktik.core.shared.diagnostics.run_halt import RunRefused


class AppVersionRefused(RunRefused):
    """The app is unpinned, its installed version is unknown, or it mismatches."""

    error_code = "APP_VERSION_REFUSED"


def require_pinned_app_version(
    device_id: str | None, package: str, platform: str | None = None
) -> str:
    """Read afresh for each startup; a prior session's version grants no authority.

    A platform may be supplied by the owner of a cloned package. Otherwise resolve
    it from the app catalog. Unknown packages and undeclared pins are refused too.
    """
    platform = platform or apps.platform_for_package(package)
    pins = apps.PINNED_VERSIONS.get(platform, ())
    label = f"{platform or 'app'} ({package})"
    if not pins:
        raise AppVersionRefused(
            device_id,
            f"No exact version pins are declared for {label}; automation refused. "
            "Declare and validate a version pin before running this app.",
        )
    expected = ", ".join(pins)
    if not isinstance(device_id, str) or not device_id.strip():
        raise AppVersionRefused(
            device_id,
            f"Cannot verify the installed version of {label} without a device serial; "
            f"automation refused. Pinned versions: {expected}. Connect the intended device.",
        )
    try:
        installed = app_inspection.get_installed_app_version(device_id, package, platform)
    except Exception as error:
        raise AppVersionRefused(
            device_id,
            f"Cannot verify the installed version of {label} on {device_id}; "
            f"automation refused. Pinned versions: {expected}. Check the device connection.",
        ) from error
    if not installed:
        raise AppVersionRefused(
            device_id,
            f"Cannot verify the installed version of {label} on {device_id}; "
            f"automation refused. Install a pinned version ({expected}) and check the device connection.",
        )
    if installed not in pins:
        raise AppVersionRefused(
            device_id,
            f"Unsupported {label} version {installed} on {device_id}; automation refused. "
            f"Pinned versions: {expected}. Install a pinned build and disable automatic updates for this app.",
        )
    return installed
