"""Post observations and explicit inspection over account-verified X browsing."""

import re

from taktik.core.shared.browsing import (
    PLATFORM_ACTIONS,
    PLATFORM_WORKFLOWS,
    ActionResult,
    FeedEmpty,
    PostObservation,
)
from taktik.core.shared.phone_interaction import Phone, Result, Status

from .engagement import available_actions
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
    states = {
        a.label: a.selected
        if a.state_visibility is not None and a.state_visibility.unobscured
        else None
        for a in post.actions
    }
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
        "engagement": {
            "liked": states.get("Like"),
            "bookmarked": states.get("Bookmark"),
        },
        "quoted_post": {
            "username": quote.author.removeprefix("@")
            if quote.author is not None
            else None,
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
    if quote is not None and quote.reply_annotation is not None:
        context["quoted_post"]["reply_annotation"] = quote.reply_annotation
        context["quoted_post"]["reply_to"] = list(quote.reply_to)
    if quote is not None and quote.nested_quote is not None:
        nested = quote.nested_quote
        context["quoted_post"]["quoted_post"] = {
            "username": nested.author.removeprefix("@")
            if nested.author is not None
            else None,
            "display_name": nested.display_name,
            "body": nested.body,
            "body_complete": nested.body_complete,
            "body_annotations": [v.text for v in nested.body_annotations],
            "author_labels": list(nested.labels),
            "translation": nested.translation,
            "media": _media_context(nested.media),
        }
        if nested.reply_annotation is not None:
            context["quoted_post"]["quoted_post"]["reply_annotation"] = (
                nested.reply_annotation
            )
            context["quoted_post"]["quoted_post"]["reply_to"] = list(nested.reply_to)
    if post.community_note is not None:
        note = post.community_note
        context["community_note"] = {
            "title": note.title,
            "body": note.body,
            "body_complete": note.body_complete,
            "translation": note.translation,
        }
    if post.market_card is not None:
        card = post.market_card
        context["market_card"] = {
            "name": card.name,
            "symbol": card.symbol,
            "price": card.price,
            "change": card.change,
            "in_viewport": card.visibility.visible_bounds is not None,
        }
        if card.adjacent_assets:
            context["market_card"]["adjacent_assets"] = [
                {
                    "label": a.text,
                    "in_viewport": a.visibility.visible_bounds is not None,
                }
                for a in card.adjacent_assets
            ]
    if post.sports_card is not None:
        card = post.sports_card
        context["sports_card"] = {
            "teams": list(card.teams),
            "status": card.status,
            "in_viewport": card.visibility.visible_bounds is not None,
        }
    return context


def _workflows(enabled_workflows):
    enabled = set(enabled_workflows)
    if not enabled or not enabled <= set(PLATFORM_WORKFLOWS["x"]):
        raise ValueError("X supports for_you, following, and search browsing.")
    return enabled


def _related_post(post):
    return {
        "username": post.author.removeprefix("@"),
        "body": post.body,
        **post_context(post),
    }


class XBrowser:
    name = "x"

    def __init__(self, phone, enabled_workflows):
        self.enabled = _workflows(enabled_workflows)
        self.phone = phone
        self.browser = X(phone)
        self.workflow = None
        self.target = ""
        self.search_tab = "top"
        self._username = None
        self._occurrence = 0
        self._valid = False
        self._clear_observation_state()

    @classmethod
    def connect(cls, serial, enabled_workflows):
        enabled = _workflows(enabled_workflows)
        return cls(Phone.connect(serial), enabled)

    @property
    def browsing_valid(self):
        return self._valid and self.browser.verified_account is not None

    def _clear_observation_state(self):
        self._media_inspection = None
        self._profile_inspection = None
        self._thread_inspection = None
        self._expanded_source_key = None
        self._post_link = None

    def start(self, username, workflow, target="", *, search_tab="top"):
        if search_tab not in {"top", "latest"} or (
            workflow != "search" and search_tab != "top"
        ):
            raise ValueError("Only X search accepts a top/latest result tab.")
        self._valid = False
        self._clear_observation_state()
        if workflow not in self.enabled or (workflow != "search" and target):
            raise ValueError(
                "X requires an enabled workflow; only search accepts a target."
            )
        if workflow == "search":
            self.browser.start(username, workflow, query=target, result_tab=search_tab)
        else:
            self.browser.start(username, workflow)
        self.workflow, self.target, self._username = workflow, target, username
        self.search_tab = search_tab
        self._occurrence += 1
        self._valid = True

    def transition(self, workflow, target="", *, search_tab="top"):
        if search_tab not in {"top", "latest"} or (
            workflow != "search" and search_tab != "top"
        ):
            raise ValueError("Only X search accepts a top/latest result tab.")
        if not self.browsing_valid:
            raise XError("X browsing context was lost; restart account verification.")
        if workflow not in self.enabled or (workflow != "search" and target):
            raise XError("Unavailable X workflow.", result=Result(Status.UNSUPPORTED))
        if (workflow, target, search_tab) != (
            self.workflow,
            self.target,
            self.search_tab,
        ):
            self.start(self._username, workflow, target, search_tab=search_tab)

    def recover(self):
        """Reverify the saved account/context and establish a new occurrence."""
        self._valid = False
        self._clear_observation_state()
        self.browser.recover()
        self.workflow = self.browser.timeline
        self.target = self.browser.query or ""
        self.search_tab = self.browser.result_tab
        self._username = self.browser.verified_account.removeprefix("@")
        self._occurrence += 1
        self._valid = True

    def observe(self, frame_count=1, interval=1.0, previous=None):
        if not self.browsing_valid:
            raise XError("Start X and verify its account before browsing.")
        post = self.browser.observe()
        if post is None:
            raise FeedEmpty(f"The X {self.workflow} timeline is empty.")
        identity_key = self._expanded_source_key or post.content_key
        identity = f"x:{self._occurrence}:{identity_key}"
        if previous is not None and previous.identity != identity:
            self._valid = False
            raise XError("X changed while gathering additional observations.")
        count = next((a.count for a in post.actions if a.label == "Like"), None)
        like_count = (
            int(count.replace(",", ""))
            if count and re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", count)
            else None
        )
        context = post_context(post)
        context["available_engagement_actions"] = available_actions(
            post,
            self.browser._screen,
            self.browser.verified_account,
            self.browser.timeline,
        )
        if self.workflow == "search":
            context["search_query"] = self.browser.query
            context["search_tab"] = self.browser.result_tab
        if self.browser.navigation_gaps:
            context["navigation_gaps"] = list(self.browser.navigation_gaps)
        profile = self._profile_inspection
        if profile is not None and profile.source_key == post.content_key:
            context["profile_inspection"] = {
                "username": profile.profile.handle.removeprefix("@"),
                "display_name": profile.profile.display_name,
                "text": [span.text for span in profile.profile.text],
                "tab": profile.tab,
                "posts": [_related_post(p) for p in profile.posts],
                "complete": False,
            }
        thread = self._thread_inspection
        if thread is not None and thread.source_key == post.content_key:
            context["thread_inspection"] = {
                "main_verified": thread.main_verified,
                "main_text": thread.main_text,
                "main_text_complete": thread.main_text_complete,
                "posts": [_related_post(p) for p in thread.posts],
                "complete": thread.complete,
                "scrolls": thread.scrolls,
                "stop_reason": thread.stop_reason,
            }
        frames = []
        inspection = self._media_inspection
        if inspection is not None and inspection.source_key == post.content_key:
            frames = list(inspection.frames)
            context["visual_content_available"] = True
            context["media_inspection"] = {
                "index": inspection.index,
                "view": inspection.view,
                "crop": inspection.crop,
                "partial": inspection.partial,
            }
        link = self._post_link
        if link is not None and link.source_key != post.content_key:
            link = None
        return PostObservation(
            username=post.author.removeprefix("@"),
            caption=post.body or "",
            identity=identity,
            workflow=self.workflow,
            platform="x",
            source_key=post.content_key,
            frames=frames,
            caption_expanded=self._expanded_source_key is not None,
            media_type="post"
            if post.media or (post.quoted_post and post.quoted_post.media)
            else "text",
            like_count=like_count,
            date_label=post.age,
            caption_type=("full" if post.body_complete else "truncated")
            if post.body is not None
            else "unknown",
            post_context=context,
            native_post_id=link.post_id if link else None,
            post_url=link.url if link else None,
        )

    def act(self, action, observation):
        if action not in PLATFORM_ACTIONS["x"]:
            raise XError(
                f"Unsupported X action: {action}.",
                result=Result(Status.UNSUPPORTED),
            )
        if action == "inspect":
            self.inspect(observation)
        elif action == "inspect_thread":
            self.inspect_thread(observation)
        elif action == "inspect_profile":
            self.visit_profile(observation)
        elif action == "read_more":
            self.read_more(observation)
        else:
            self._selected(observation)
            operations = {
                "like": self.browser.set_liked,
                "save": self.browser.set_bookmarked,
                "follow": self.browser.follow,
                "unfollow": self.browser.unfollow,
                "not_interested": self.browser.not_interested,
            }
            if action in operations:
                result = operations[action]()
                if result.advanced:
                    self._occurrence += 1
                    self._clear_observation_state()
                return ActionResult(advanced=result.advanced)
        return ActionResult()

    def _selected(self, observation):
        current = self.observe()
        if observation.platform != "x" or observation.identity != current.identity:
            self._valid = False
            raise XError("The X decision does not refer to the current post.")
        return current

    def visit_profile(self, observation):
        self._selected(observation)
        self._profile_inspection = self.browser.visit_profile()
        return self._profile_inspection

    def copy_link(self, observation):
        self._selected(observation)
        self._post_link = self.browser.copy_link()
        return self._post_link

    def inspect_thread(self, observation, *, max_posts=10, max_scrolls=4):
        self._selected(observation)
        self._thread_inspection = self.browser.inspect_thread(
            max_posts=max_posts, max_scrolls=max_scrolls
        )
        return self._thread_inspection

    def inspect(self, observation, *, index=0, frame_count=1, interval=1.0):
        self._selected(observation)
        self._media_inspection = self.browser.inspect_media(
            index, frame_count=frame_count, interval=interval
        )
        return self._media_inspection

    def read_more(self, observation):
        current = self._selected(observation)
        post = self.browser.read_more()
        if post.content_key != current.source_key:
            self._expanded_source_key = self._expanded_source_key or current.source_key
            self._media_inspection = None
            self._profile_inspection = None
            self._thread_inspection = None
            self._post_link = None

    def advance(self):
        if not self.browsing_valid:
            raise XError("X browsing context was lost; restart account verification.")
        self.browser.advance()
        self._occurrence += 1
        self._clear_observation_state()
