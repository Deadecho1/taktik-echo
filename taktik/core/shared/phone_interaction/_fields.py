"""Constrained editable-field discovery for native screens without resource IDs."""

from dataclasses import dataclass

from lxml import etree

from taktik.core.shared.ui.geometry import bounds

from ._session import InteractionError


@dataclass(frozen=True)
class TextField:
    """The unique EditText in a package and resource-ID screen scope.

    Text and focus are read afresh throughout typing. Neither coordinates nor
    mutable query text identify the field.
    """

    package: str
    scope_resource_id: str

    def __post_init__(self):
        if not all(
            isinstance(value, str) and value.strip()
            for value in (self.package, self.scope_resource_id)
        ):
            raise ValueError("A text field requires a package and screen scope.")


def _contains(outer, inner):
    return (
        outer is not None
        and inner is not None
        and outer[0] <= inner[0] < inner[2] <= outer[2]
        and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def resolve_field(xml, size, locator):
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml, parser)
    except etree.XMLSyntaxError as error:
        raise InteractionError("Cannot read the text field hierarchy.") from error
    if root.tag != "hierarchy" or root.getroottree().docinfo.doctype:
        raise InteractionError("Cannot read the text field hierarchy.")
    windows = [node for node in root if node.get("package") == locator.package]
    if len(windows) != 1:
        raise InteractionError("The text field window is missing or ambiguous.")
    window = windows[0]
    scopes = window.xpath(".//*[@resource-id=$scope]", scope=locator.scope_resource_id)
    fields = window.xpath('.//*[@class="android.widget.EditText"]')
    if (
        len(scopes) != 1
        or len(fields) != 1
        or scopes[0] not in fields[0].iterancestors()
    ):
        raise InteractionError("The text field is missing or ambiguous in its scope.")
    field = fields[0]
    ancestors = [field, *field.iterancestors()]
    if (
        any(
            node.get("package") != locator.package
            or node.get("enabled") != "true"
            or node.get("visible-to-user") == "false"
            for node in ancestors
            if node is not root
        )
        or field.get("password") == "true"
        or field.get("focusable") != "true"
    ):
        raise InteractionError("The requested text field is not usable.")
    rect = bounds(field)
    if not all(
        _contains(outer, rect)
        for outer in ((0, 0, *size), bounds(window), bounds(scopes[0]))
    ):
        raise InteractionError("The text field is clipped or has invalid bounds.")
    for other in root:
        if other is window:
            continue
        other_rect = bounds(other)
        if other_rect is None or _overlaps(rect, other_rect):
            raise InteractionError("An external window obscures the text field.")
    related = {*ancestors, *field.iterdescendants()}
    for node in window.iter():
        if node in related or not any(
            node.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "scrollable")
        ):
            continue
        other_rect = bounds(node)
        if other_rect is None or _overlaps(rect, other_rect):
            raise InteractionError("Another app control obscures the text field.")
    exclusions = []
    for node in field.iterdescendants():
        if any(
            node.get(flag) == "true"
            for flag in ("clickable", "long-clickable", "scrollable")
        ):
            child_rect = bounds(node)
            if child_rect is None:
                raise InteractionError("A nested field control has invalid bounds.")
            exclusions.append(child_rect)
    return {
        "className": field.get("class"),
        "text": field.get("text", ""),
        "focused": field.get("focused") == "true",
        "bounds": dict(zip(("left", "top", "right", "bottom"), rect)),
        "exclude": tuple(exclusions),
    }
