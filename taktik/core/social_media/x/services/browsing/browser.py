"""Text-only post observations over account-verified X timeline browsing."""

import re

from taktik.core.shared.browsing import (
    PLATFORM_ACTIONS,
    PLATFORM_WORKFLOWS,
    ActionResult,
    FeedEmpty,
    PostObservation,
)
from taktik.core.shared.phone_interaction import Phone, Result, Status

from .navigation import X, XError


def _media_context(media):
    return [
        {
            "kind": item.kind,
            "description": item.description,
            "source_label": item.source_label,
            "source_prefix": item.source_prefix,
            "preview_text": item.preview_text,
            "in_viewport": item.visibility.visible_bounds is not None,
        }
        for item in media
    ]


def post_context(post):
    quote = post.quoted_post
    context = {
        "display_name": post.display_name,
        "body_complete": post.body_complete,
        "body_annotations": list(post.body_annotations),
        "age_label": post.age,
        "reposted_by": post.reposted_by,
        "reply_annotation": post.reply_annotation,
        "reply_to": list(post.reply_to),
        "author_labels": list(post.labels),
        "translation": post.translation,
        "media_labels": list(post.media_labels),
        "media_tags": list(post.media_tags),
        "advertising": post.advertising,
        "visual_content_available": False,
        "media": _media_context(post.media),
        "counts": {action.label: action.count for action in post.actions},
        "quoted_post": {
            "username": quote.author.removeprefix("@"),
            "display_name": quote.display_name,
            "body": quote.body,
            "body_complete": quote.body_complete,
            "body_annotations": [v.text for v in quote.body_annotations],
            "author_labels": list(quote.labels),
            "translation": quote.translation,
            "media": _media_context(quote.media),
        }
        if quote
        else None,
    }
    if quote is not None and quote.footer_annotations:
        context["quoted_post"]["footer_annotations"] = [
            v.text for v in quote.footer_annotations
        ]
    if quote is not None and quote.nested_quote is not None:
        nested = quote.nested_quote
        context["quoted_post"]["quoted_post"] = {
            "username": nested.author.removeprefix("@"),
            "display_name": nested.display_name,
            "body": nested.body,
            "body_complete": nested.body_complete,
            "body_annotations": [v.text for v in nested.body_annotations],
            "author_labels": list(nested.labels),
            "translation": nested.translation,
            "media": _media_context(nested.media),
        }
    if post.community_note is not None:
        note = post.community_note
        context["community_note"] = {
            "title": note.title,
            "body": note.body,
            "body_complete": note.body_complete,
            "translation": note.translation,
        }
    return context


def _workflows(enabled_workflows):
    enabled = set(enabled_workflows)
    if not enabled or not enabled <= set(PLATFORM_WORKFLOWS["x"]):
        raise ValueError("X supports only for_you and following timeline browsing.")
    return enabled


class XBrowser:
    name = "x"

    def __init__(self, phone, enabled_workflows):
        self.enabled = _workflows(enabled_workflows)
        self.phone = phone
        self.browser = X(phone)
        self.workflow = None
        self._username = None
        self._occurrence = 0
        self._valid = False

    @classmethod
    def connect(cls, serial, enabled_workflows):
        enabled = _workflows(enabled_workflows)
        return cls(Phone.connect(serial), enabled)

    @property
    def browsing_valid(self):
        return self._valid and self.browser.verified_account is not None

    def start(self, username, workflow, target=""):
        self._valid = False
        if workflow not in self.enabled or target:
            raise ValueError("X requires an enabled timeline and no target.")
        self.browser.start(username, workflow)
        self.workflow, self._username = workflow, username
        self._occurrence += 1
        self._valid = True

    def transition(self, workflow, target=""):
        if not self.browsing_valid:
            raise XError("X browsing context was lost; restart account verification.")
        if workflow not in self.enabled or target:
            raise XError("Unavailable X workflow.", result=Result(Status.UNSUPPORTED))
        if workflow != self.workflow:
            self.start(self._username, workflow)

    def observe(self, frame_count=1, interval=1.0, previous=None):
        if not self.browsing_valid:
            raise XError("Start X and verify its account before browsing.")
        post = self.browser.observe()
        if post is None:
            raise FeedEmpty(f"The X {self.workflow} timeline is empty.")
        identity = f"x:{self._occurrence}:{post.content_key}"
        if previous is not None and previous.identity != identity:
            self._valid = False
            raise XError("X changed while gathering additional observations.")
        count = next((a.count for a in post.actions if a.label == "Like"), None)
        like_count = (
            int(count.replace(",", ""))
            if count and re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", count)
            else None
        )
        return PostObservation(
            username=post.author.removeprefix("@"),
            caption=post.body or "",
            identity=identity,
            workflow=self.workflow,
            platform="x",
            source_key=post.content_key,
            media_type="post"
            if post.media or (post.quoted_post and post.quoted_post.media)
            else "text",
            like_count=like_count,
            date_label=post.age,
            caption_type=("full" if post.body_complete else "truncated")
            if post.body is not None
            else "unknown",
            post_context=post_context(post),
        )

    def act(self, action, observation):
        if action not in PLATFORM_ACTIONS["x"]:
            raise XError(
                "X currently supports only watch and skip.",
                result=Result(Status.UNSUPPORTED),
            )
        current = self.observe()
        if observation.platform != "x" or observation.identity != current.identity:
            self._valid = False
            raise XError("The X decision does not refer to the current post.")
        return ActionResult()

    def advance(self):
        if not self.browsing_valid:
            raise XError("X browsing context was lost; restart account verification.")
        self.browser.advance()
        self._occurrence += 1
