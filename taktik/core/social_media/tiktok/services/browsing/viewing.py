"""Viewing-only adjustments to the pinned upstream For You workflow."""

import math

from taktik.core.shared.phone_interaction import InteractionError, SessionExpired
from taktik.core.social_media.tiktok.services.behavior.watch_time import (
    video_watch_seconds,
)
from taktik.core.social_media.tiktok.workflows.automation.for_you.payload import (
    for_you_config_from_payload,
)
from taktik.core.social_media.tiktok.workflows.common.models import VideoWorkflowStats


def validate_config(raw):
    config = for_you_config_from_payload(raw)
    for name in (
        "like_probability",
        "follow_probability",
        "favorite_probability",
        "comment_probability",
        "repost_probability",
        "max_likes_per_session",
        "max_follows_per_session",
        "max_comments_per_session",
        "max_reposts_per_session",
        "training_reject_off_niche",
        "max_rejections_per_session",
        "follow_back_suggestions",
    ):
        if getattr(config, name) != 0:
            raise ValueError(
                f"Viewing-only preset enables {name}; expected zero or false."
            )
    if config.training_keywords or config.comment_texts:
        raise ValueError(
            "Viewing-only sessions must leave training keywords and comments empty."
        )
    if not 1 <= config.max_videos <= 500:
        raise ValueError("maxVideos must be between 1 and 500.")
    if not all(
        math.isfinite(value) for value in (config.min_watch_time, config.max_watch_time)
    ):
        raise ValueError("Watch times must be finite numbers.")
    if not 0 < config.min_watch_time <= config.max_watch_time <= 300:
        raise ValueError(
            "Watch times must be positive, ordered, and at most 300 seconds."
        )
    return config


class ViewingForYouWorkflow:
    """Viewing-only workflow with the same count, watch bounds and suggestion stop."""

    def __init__(self, app, config):
        self.app, self.config = app, config
        self.stats = VideoWorkflowStats()
        self._running = False

    def stop(self):
        self._running = False

    def _filtered(self, info):
        if self.config.skip_already_liked and info.get("is_liked"):
            return True
        count = info.get("like_count")
        if count is not None and (
            (self.config.min_likes and count < self.config.min_likes)
            or (self.config.max_likes and count > self.config.max_likes)
        ):
            return True
        caption = info.get("description", "").casefold()
        return bool(
            (
                self.config.required_hashtags
                and not any(
                    f"#{tag.casefold()}" in caption
                    for tag in self.config.required_hashtags
                )
            )
            or any(
                f"#{tag.casefold()}" in caption for tag in self.config.excluded_hashtags
            )
        )

    def run(self):
        self._running = True
        previous = None
        try:
            self.app.transition("for_you", "")
            while self._running and self.stats.videos_watched < self.config.max_videos:
                kind, info = self.app.viewing_screen()
                if kind == "suggestion":
                    self.stats.completion_reason = "suggestion_needs_manual_input"
                    break
                if kind == "live" or (kind == "ad" and self.config.skip_ads):
                    if kind == "ad":
                        self.stats.ads_skipped += 1
                    else:
                        self.stats.lives_skipped += 1
                    self.app.advance()
                    continue
                if kind not in ("post", "ad"):
                    self.stats.completion_reason = "screen_needs_manual_input"
                    break
                if info["identity"] == previous:
                    self.stats.completion_reason = "stuck_video"
                    self.stats.errors += 1
                    break
                previous = info["identity"]
                seconds = video_watch_seconds(
                    info,
                    minimum=self.config.min_watch_time,
                    maximum=self.config.max_watch_time,
                    reading_scale=self.app.phone.reading_scale(),
                )
                self.app.phone.wait(seconds, purpose="viewing")
                self.stats.videos_watched += 1
                if self._filtered(info):
                    self.stats.videos_skipped += 1
                if self.stats.videos_watched >= self.config.max_videos:
                    self.stats.completion_reason = "video_limit"
                    break
                self.app.advance()
        except SessionExpired:
            self.stats.completion_reason = "session_duration"
        except InteractionError:
            self.stats.errors += 1
            self.stats.completion_reason = "interaction_failed"
            raise
        finally:
            self._running = False
        return self.stats


def run_viewing(raw, *, startup, workflow_factory=ViewingForYouWorkflow):
    config = validate_config(raw)
    workflow = workflow_factory(startup(), config)
    stats = workflow.run().to_dict()
    return {
        "success": stats["errors"] == 0
        and stats["videos_watched"] == config.max_videos,
        "stats": stats,
    }
