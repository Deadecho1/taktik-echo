"""Bounded Instagram Home viewing through the verified browsing service."""

from taktik.core.shared.phone_interaction import SessionExpired


def instagram_viewing(app, raw):
    from taktik.core.social_media.instagram.actions.base.stats import (
        create_workflow_stats,
    )
    from taktik.core.social_media.instagram.workflows.automation.config_builder import (
        build_instagram_automation_config,
    )
    from taktik.core.social_media.instagram.workflows.automation.workflow_defaults import (
        FEED_DEFAULTS,
    )
    from taktik.core.social_media.instagram.workflows.common.interaction_config import (
        merge_operator_config,
    )

    built = build_instagram_automation_config(raw)
    config = merge_operator_config(FEED_DEFAULTS, built["actions"][0])
    stats = create_workflow_stats("feed")
    app.transition("home", "")
    filler = 0
    try:
        for _ in range(config["max_posts_to_check"]):
            stats["posts_checked"] += 1
            kind = app.viewing_screen()
            if kind == "ad" and config["skip_ads"]:
                stats["posts_skipped_ads"] += 1
            elif kind == "reel" and config.get("skip_reels"):
                stats["posts_skipped_reels"] = stats.get("posts_skipped_reels", 0) + 1
            else:
                app.scroll.human_reading_pause(
                    read_captions=config["read_captions"],
                    browse_carousels=config["browse_carousels"],
                )
            result = app.scroll.scroll_feed_to_next_post(
                skip_ads=config["skip_ads"], skip_suggested=config["skip_suggested"]
            )
            stats["posts_skipped_ads"] += result.get("ads_skipped", 0)
            stats["posts_skipped_suggested"] = stats.get(
                "posts_skipped_suggested", 0
            ) + result.get("suggested_skipped", 0)
            if not result.get("on_feed"):
                stats["stop_reason"] = "left_feed"
                break
            filler = filler + 1 if result.get("filler_run") else 0
            if filler >= 2:
                stats["stop_reason"] = "feed_tail"
                break
        else:
            stats["stop_reason"] = "posts_cap"
    except SessionExpired:
        stats["stop_reason"] = "session_duration"
    stats["success"] = True
    return stats
