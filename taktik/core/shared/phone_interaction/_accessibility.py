"""A temporary native hierarchy read with screen-reader semantics enabled."""

import base64
import binascii
import shlex
import uuid
from pathlib import Path

from lxml import etree

from ._session import InteractionError

_MARKER = "TAKTIK_HIERARCHY_V1:"


def _shell(backend, command, *, timeout=5):
    result = backend._call("shell", command, timeout=timeout)
    if result.exit_code != 0:
        raise InteractionError("The native accessibility reader command failed.")
    return result.output


def _released(backend):
    for _ in range(50):
        if "Ui Automation[" not in _shell(backend, ["dumpsys", "accessibility"]):
            return
        backend.phone.wait(0.1, purpose="readiness")
    raise InteractionError("The native accessibility service did not disconnect.")


def _decode(output):
    records = [line for line in output.splitlines() if line.startswith(_MARKER)]
    if len(records) != 1:
        raise InteractionError(
            "The native accessibility reader returned no unique hierarchy."
        )
    try:
        xml = base64.b64decode(records[0][len(_MARKER) :], validate=True).decode(
            "utf-8"
        )
        root = etree.fromstring(
            xml.encode("utf-8"),
            parser=etree.XMLParser(resolve_entities=False, no_network=True),
        )
    except (binascii.Error, UnicodeError, etree.XMLSyntaxError) as error:
        raise InteractionError(
            "The native accessibility hierarchy is invalid."
        ) from error
    if root.tag != "hierarchy" or root.getroottree().docinfo.doctype:
        raise InteractionError("The native accessibility hierarchy is invalid.")
    return xml


def read_hierarchy(backend):
    raw, phone = backend._raw, backend.phone
    asset = Path(__file__).with_name("native") / "hierarchy-reader.dex"
    if not asset.is_file() or getattr(raw, "_process", None) is None:
        raise NotImplementedError(
            "The Phone session must own its native hierarchy reader."
        )
    remote = f"/data/local/tmp/taktik-hierarchy-{uuid.uuid4().hex}.dex"
    config = raw.jsonrpc.getConfigurator()
    stopped = False
    try:
        phone._check()
        raw.adb_device.sync.push(str(asset), remote, check=True)
        stopped = True
        backend._call("stop_uiautomator", wait=False)
        _released(backend)
        classpath = shlex.quote(remote + ":/data/local/tmp/u2.jar")
        output = _shell(
            backend,
            f"CLASSPATH={classpath} app_process / taktik.phone.HierarchyReader",
            timeout=15,
        )
    finally:
        with phone.cleanup():
            try:
                if stopped:
                    _released(backend)
                    backend._call("start_uiautomator")
                    if raw.jsonrpc.setConfigurator(config) != config:
                        raise InteractionError(
                            "The native reader configuration was not restored."
                        )
            finally:
                _shell(backend, ["rm", "-f", remote])
    phone._check()
    return _decode(output)
