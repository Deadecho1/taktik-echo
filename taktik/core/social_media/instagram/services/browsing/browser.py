import hashlib
import io
import re
from contextlib import suppress
from datetime import datetime, timezone

from taktik.core.shared.browsing import PlatformError, PostObservation
from taktik.core.shared.phone_interaction import Phone, Result, Status
from taktik.core.shared.ui.geometry import bounds, nodes, text_of
from taktik.core.social_media.instagram.services.browsing.framing import HomeScroll
from taktik.core.social_media.instagram.ui.posts import (
    PACKAGE,
    read_post,
    read_scrolled_post_time,
    resource,
    same_content,
)

UTC = timezone.utc


class HomeWorkflow:
    def enter(self, app, target):
        app.go_tab("feed_tab")
        app.scroll.land_on_post_header()
        try:
            app._view()
        except PlatformError:
            self.advance(app)

    def advance(self, app):
        app.scroll.scroll_feed_to_next_post(skip_ads=False, skip_suggested=False)


class ReelsWorkflow:
    def enter(self, app, target):
        app.go_tab("clips_tab")

    def advance(self, app):
        app.phone.gesture(
            "page", "up", (0, app.height * 0.1, app.width * 0.8, app.height * 0.88)
        ).require()
        app.sleep(0.7)


class GridWorkflow:
    def __init__(self):
        self.seen = set()
        self.cursor = 0

    def _tiles(self, app, root):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import (
            POST_SELECTORS,
        )

        return nodes(
            root,
            [
                POST_SELECTORS.first_post_grid,
                resource("media_thumbnail"),
                resource("clips_grid_image"),
            ],
            (0, 0, app.width, app.height),
        )

    def open_next(self, app):
        for _ in range(4):
            root = app.snapshot()
            tiles = self._tiles(app, root)
            image = app.phone.read("screenshot") if tiles else None
            for index, tile in enumerate(tiles):
                rect = bounds(tile)
                if index < self.cursor:
                    continue
                digest = hashlib.sha256(
                    image.crop(rect).resize((32, 32)).tobytes()
                ).hexdigest()
                if digest in self.seen:
                    continue
                if len(self.seen) >= 1000:
                    self.seen.clear()
                self.seen.add(digest)
                self.cursor = index + 1
                app.tap(tile)
                app.sleep(1)
                return
            self._scroll_grid(app)
            app.sleep(0.6)
            self.cursor = 0
        raise PlatformError("No new post thumbnail could be opened from the grid.")

    def _scroll_grid(self, app):
        app.phone.gesture(
            "scroll",
            "up",
            (0, app.height * 0.12, app.width, app.height * 0.92),
            distance=app.height * 0.6,
        ).require()

    def advance(self, app):
        for _ in range(4):
            if self._tiles(app, app.snapshot()):
                self.open_next(app)
                return
            app.phone.command("back").require()
            app.sleep(0.5)
        raise PlatformError("Cannot return to the workflow's post grid.")


class ExploreWorkflow(GridWorkflow):
    def enter(self, app, target):
        self.seen.clear()
        self.cursor = 0
        app.go_tab("search_tab")
        self.open_next(app)


class SearchWorkflow(GridWorkflow):
    def _scroll_grid(self, app):
        # Search cards need most of the usable list height to leave the screen.
        app.phone.drag(
            (app.width * 0.45, app.height * 0.90, app.width * 0.55, app.height * 0.93),
            (app.width * 0.45, app.height * 0.12, app.width * 0.55, app.height * 0.15),
            region=(0, app.height * 0.1, app.width, app.height * 0.95),
        ).require()

    def _tiles(self, app, root):
        cards = nodes(
            root,
            [
                resource("grid_card_layout_container")
                + f'//*[@resource-id="{PACKAGE}:id/media_container"]'
            ],
            (0, 0, app.width, app.height),
        )
        return cards or super()._tiles(app, root)

    def enter(self, app, target):
        self.seen.clear()
        self.cursor = 0
        if not target.strip():
            raise PlatformError(
                "Search requires a query; set session.start_target when starting in search."
            )
        app.go_tab("search_tab")
        app.tap_control([resource("action_bar_search_edit_text")])
        app.phone.enter_text(
            f"{PACKAGE}:id/action_bar_search_edit_text", target, submit="enter"
        ).require()
        app.sleep(1.5)
        self.open_next(app)


class ProfileWorkflow(GridWorkflow):
    def enter(self, app, target):
        self.seen.clear()
        self.cursor = 0
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", target):
            raise PlatformError("Profile browsing requires an exact username.")
        app.open_profile(target)
        self.open_next(app)


class Instagram:
    name = "instagram"

    def __init__(self, phone, enabled_workflows, *, scroll=None):
        self.phone = phone
        self.scroll = scroll if scroll is not None else HomeScroll(phone)
        self.enabled = set(enabled_workflows)
        self.sleep = lambda seconds: phone.wait(seconds, purpose="readiness")
        self.width, self.height = phone.read("size")
        self.workflows = {
            "home": HomeWorkflow(),
            "reels": ReelsWorkflow(),
            "explore": ExploreWorkflow(),
            "search": SearchWorkflow(),
            "profile": ProfileWorkflow(),
        }
        self.workflow = "home"
        self.expanded = False
        self.auto_advanced = False
        self.caption_open = False

    def start_current_account(self):
        self.phone.command("launch", PACKAGE).require()
        self.sleep(1)
        self.go_tab("profile_tab")
        return self._active_username()

    @classmethod
    def connect(cls, serial, enabled_workflows):
        return cls(Phone.connect(serial), enabled_workflows)

    def open_profile(self, username):
        self.phone.command(
            "open_url", (PACKAGE, f"https://www.instagram.com/{username}/")
        ).require()
        for _ in range(10):
            if self._active_username().casefold() == username.casefold():
                return
            self.sleep(0.3)
        raise PlatformError("Cannot verify the requested Instagram profile.")

    def snapshot(self):
        try:
            from taktik.core.shared.device.snapshot import ScreenSnapshot

            root = ScreenSnapshot(self.phone.read("hierarchy")).root
            # Android 16 can report the launcher as resumed while Instagram is visibly active.
            visible_app = [
                n for n in root.iter() if n.get("package") == PACKAGE and bounds(n)
            ]
            if not any(
                (bounds(n)[2] - bounds(n)[0]) * (bounds(n)[3] - bounds(n)[1])
                >= self.width * self.height * 0.5
                for n in visible_app
            ):
                raise PlatformError("Instagram is not the foreground app.")
            return root
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Cannot read Instagram's screen ({type(error).__name__})."
            ) from error

    def tap(self, node):
        self.phone.tap(bounds(node)).require()

    def tap_control(self, selectors, within=None):
        choices = nodes(self.snapshot(), selectors, within)
        if len(choices) != 1:
            raise PlatformError(
                "The requested control is missing or ambiguous on this screen."
            )
        self.tap(choices[0])

    def go_tab(self, name):
        previous_bounds = None
        for _ in range(10):
            choices = nodes(
                self.snapshot(), [resource(name)], (0, 0, self.width, self.height)
            )
            if len(choices) == 1:
                if any(n.get("selected") == "true" for n in choices[0].iter()):
                    return
                current_bounds = bounds(choices[0])
                # Launch animations expose tab coordinates before they stop moving.
                if current_bounds == previous_bounds:
                    self.tap(choices[0])
                    self.sleep(0.7)
                    previous_bounds = None
                else:
                    previous_bounds = current_bounds
                    self.sleep(0.3)
            else:
                previous_bounds = None
                self.phone.command("back").require()
                self.sleep(0.4)
        raise PlatformError(f"Cannot open the Instagram {name} navigation tab.")

    def _active_username(self):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        for _ in range(10):
            names = nodes(
                self.snapshot(),
                PROFILE_SELECTORS.username,
                (0, 0, self.width, self.height),
            )
            if len(names) == 1:
                username = text_of(names[0]).strip().lstrip("@")
                if re.fullmatch(r"[A-Za-z0-9_.]{1,30}", username):
                    return username
            self.sleep(0.3)
        raise PlatformError(
            "Cannot read the active Instagram username from the profile."
        )

    def start(self, username, workflow, target=""):
        self.phone.command("launch", PACKAGE).require()
        for attempt in range(10):
            try:
                self.snapshot()
                break
            except PlatformError:
                if attempt == 9:
                    raise
                self.sleep(0.3)
        self.go_tab("profile_tab")
        if self._active_username().casefold() != username.casefold():
            raise PlatformError(
                "The active Instagram username does not match the configured account mapping."
            )
        self.transition(workflow, target)

    def transition(self, workflow, target):
        if workflow not in self.enabled:
            raise PlatformError("The requested workflow is disabled.")
        self._close_caption()
        try:
            self.workflows[workflow].enter(self, target)
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Workflow navigation failed ({type(error).__name__})."
            ) from error
        self.workflow = workflow
        self.expanded = False

    def _view(self):
        return read_post(self.snapshot(), self.width, self.height)

    def viewing_screen(self):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import (
            FEED_SELECTORS,
        )

        root = self.snapshot()
        if nodes(root, FEED_SELECTORS.sponsored_indicators):
            return "ad"
        return "reel" if nodes(root, FEED_SELECTORS.reel_indicators) else "post"

    def observe(self, frame_count, interval, previous=None):
        try:
            view = self._view()
            if previous and not same_content(view, previous, self.expanded):
                raise PlatformError(
                    "The post changed while gathering additional observations."
                )
            frames = list(previous.frames) if previous else []
            for index in range(frame_count):
                if index:
                    self.phone.wait(interval, purpose="frame")
                image = self.phone.read("screenshot").crop(view.crop).convert("RGB")
                image.thumbnail((1024, 1024))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=80)
                frames.append(buffer.getvalue())
            after = self._view()
            baseline = PostObservation(
                view.username, view.caption, view.identity, self.workflow
            )
            if not same_content(after, baseline):
                raise PlatformError("The post changed during frame capture.")
            post_time = (
                previous.post_time
                if previous and previous.post_time is not None
                else view.post_time or after.post_time
            )
            if previous is None and post_time is None and not view.reel:
                post_time = self._peek_post_time(view)
            self.expanded = False
            return PostObservation(
                view.username,
                view.caption,
                view.identity,
                self.workflow,
                frames[-6:],
                view.visible_text,
                like_count=(
                    previous.like_count
                    if previous and previous.like_count is not None
                    else view.like_count
                ),
                post_time=post_time,
            )
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Content capture failed ({type(error).__name__})."
            ) from error

    def _peek_post_time(self, view):
        top = max(view.crop[1], int(self.height * 0.2))
        start = min(view.crop[3], int(self.height * 0.8))
        distance = min(int(self.height * 0.18), (start - top) // 2)
        if distance <= 0:
            return None
        x = self.width // 2
        margin = max(5, int(self.width * 0.025))
        first = (x - margin, start - margin, x + margin, start + margin)
        last = (
            x - margin,
            start - distance - margin,
            x + margin,
            start - distance + margin,
        )
        region = (0, top, self.width, min(self.height, start + margin + 1))
        self.phone.drag(first, last, region=region).require()
        try:
            self.sleep(0.4)
            post_time = read_scrolled_post_time(
                self.snapshot(), view, self.width, self.height, datetime.now(UTC)
            )
        finally:
            with self.phone.cleanup():
                self.phone.drag(last, first, region=region).require()
                self.sleep(0.4)
        if not same_content(self._view(), view):
            raise PlatformError("The post changed while checking its date.")
        return post_time

    def _current(self, observation, allow_caption_change=False):
        view = self._view()
        if not same_content(view, observation, allow_caption_change):
            raise PlatformError(
                "The observed post is no longer on screen; action discarded."
            )
        return view

    def read_more(self, observation):
        view = self._current(observation)
        if view.reel:
            from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import (
                POST_SELECTORS,
            )

            captions = nodes(
                view.root, POST_SELECTORS.reel_caption_selectors, view.crop
            )
            target = next((n for n in captions if text_of(n).strip()), None)
            if target is None:
                raise PlatformError("This reel has no available caption to expand.")
            self.tap(target)
            self.caption_open = True
        else:
            try:
                self.scroll._last_reveal_scroll_px = 0
                if not self.scroll.expand_caption_if_truncated():
                    raise PlatformError("This post has no available caption expander.")
                distance = self.scroll._last_reveal_scroll_px
                if distance and not self.scroll._reframe_post_after_reading(distance):
                    raise PlatformError(
                        "Could not reframe the post after reading its caption."
                    )
            except PlatformError:
                raise
            except Exception as error:
                raise PlatformError(
                    f"Caption expansion failed ({type(error).__name__})."
                ) from error
            finally:
                self.scroll._last_reveal_scroll_px = 0
        self.sleep(0.5)
        self.expanded = True

    def _open_post_menu(self, view):
        controls = nodes(
            view.root,
            [
                resource(name)
                for name in (
                    "media_option_button",
                    "row_feed_button_more",
                    "clips_more_action",
                    "clips_ufi_more_button_component",
                    "more_button",
                )
            ]
            + ['//*[@content-desc="More options"]'],
            view.crop,
        )
        if len(controls) != 1:
            raise PlatformError("No unambiguous menu control for the observed post.")
        self.tap(controls[0])
        self.sleep(0.4)
        sheets = nodes(
            self.snapshot(),
            [
                resource("layout_container_bottom_sheet"),
                resource("bottom_sheet_container"),
            ],
        )
        if not sheets:
            raise PlatformError("The post menu did not open.")
        return sheets[-1]

    @staticmethod
    def _unconfirmed(action):
        message = (
            f"Instagram did not confirm {action}; the action will not be repeated."
        )
        raise PlatformError(message, result=Result(Status.UNCERTAIN, detail=message))

    def _verify_menu_change(self, action, view):
        expected = {
            "save": ("Saved", "Remove from saved"),
            "follow": ("Following", "Unfollow", "Requested"),
            "unfollow": ("Follow", "Follow back"),
        }[action]
        opened = False
        try:
            current = self._current(view, allow_caption_change=True)
            sheet = self._open_post_menu(current)
            opened = True
            labels = {text_of(n).strip() for n in sheet.iter()}
            if not labels.intersection(expected):
                self._unconfirmed(action)
        except PlatformError as error:
            if error.result.status != Status.FAILED:
                raise
            self._unconfirmed(action)
        finally:
            if opened:
                with self.phone.cleanup():
                    self.phone.command("back").require()

    def _menu_action(self, name, view):
        labels = {
            "save": ("Save", "Saved", "Remove from saved"),
            "follow": ("Follow", "Following", "Requested"),
            "unfollow": ("Unfollow",),
            "not_interested": ("Not interested",),
        }[name]
        submitted = False
        try:
            sheet = self._open_post_menu(view)
            choices = nodes(
                sheet,
                [
                    f'.//*[@text="{label}" or @content-desc="{label}"]'
                    for label in labels
                ],
            )
            choices = [
                n
                for n in choices
                if not any(
                    n in other.iterancestors() for other in choices if other is not n
                )
            ]
            if len(choices) != 1:
                raise PlatformError(f"{name} is unavailable in the current post menu.")
            if text_of(choices[0]) in (
                "Saved",
                "Remove from saved",
                "Following",
                "Requested",
            ):
                self.phone.command("back").require()
                return
            submitted = True
            self.tap(choices[0])
            self.sleep(0.5)
            if name == "unfollow":
                confirm = nodes(
                    self.snapshot(), ['//*[@text="Unfollow" and @clickable="true"]']
                )
                if len(confirm) == 1:
                    self.tap(confirm[0])
            if name == "not_interested":
                for _ in range(4):
                    current = self._view()
                    if not same_content(current, view, expanded=True):
                        self.auto_advanced = True
                        return
                    self.sleep(0.3)
                self._unconfirmed(name)
            if name == "save":
                self._close_save_sheet()
            self._verify_menu_change(name, view)
        except Exception as error:
            with self.phone.cleanup(), suppress(Exception):
                self.phone.command("back").require()
            if (
                isinstance(error, PlatformError)
                and error.result.status != Status.FAILED
            ):
                raise
            if submitted:
                self._unconfirmed(name)
            if isinstance(error, PlatformError):
                raise
            raise PlatformError(
                f"Post menu action failed ({type(error).__name__})."
            ) from error

    def act(self, action, observation):
        if action in ("skip", "watch"):
            return
        expanded = self.caption_open
        self._close_caption()
        view = self._current(observation, expanded)
        if action in ("like", "save"):
            options = (
                [resource("row_feed_button_like"), resource("like_button")]
                if action == "like"
                else [resource("row_feed_button_save"), resource("save_button")]
            )
            choices = nodes(view.root, options, view.crop)
            if action == "like" and not choices and not view.reel:
                view = self._show_post_buttons(view)
                choices = nodes(view.root, options, view.crop)
            if len(choices) == 1:
                target = choices[0]
                if target.get("selected") == "true" or text_of(target).lower() in (
                    "unlike",
                    "liked",
                    "saved",
                    "remove from saved",
                ):
                    return
                if action == "like" and view.reel and self._red_heart(target):
                    return
                self.tap(target)
                self.sleep(0.4)
                if action == "save":
                    self._close_save_sheet()
                self._verify_toggle(action, view, options)
                return
            if action == "like":
                raise PlatformError(
                    "No unambiguous like control for the observed post."
                )
        if action == "follow":
            follow = nodes(
                view.root,
                [
                    resource("inline_follow_button"),
                    resource("row_feed_profile_header_follow_button"),
                ],
                view.crop,
            )
            if len(follow) == 1:
                if text_of(follow[0]).strip().lower() in ("following", "requested"):
                    return
                if text_of(follow[0]).strip().lower() in ("follow", "follow back"):
                    self.tap(follow[0])
                    self.sleep(0.5)
                    self._verify_menu_change("follow", view)
                    return
        if action == "unfollow" and "profile" in self.enabled:
            try:
                self._unfollow_author(observation)
            except PlatformError:
                raise
            except Exception as error:
                raise PlatformError(
                    f"Unfollow failed ({type(error).__name__})."
                ) from error
            return
        if action in ("follow", "unfollow", "save", "not_interested"):
            self._menu_action(action, view)
            if action == "save":
                self._close_save_sheet()
            return
        raise PlatformError("Unsupported consumption action.")

    def _verify_toggle(self, action, reference, selectors):
        for _ in range(4):
            current = self._current(reference, allow_caption_change=True)
            choices = nodes(current.root, selectors, current.crop)
            if len(choices) == 1:
                target = choices[0]
                if target.get("selected") == "true" or text_of(target).casefold() in (
                    "unlike",
                    "liked",
                    "saved",
                    "remove from saved",
                ):
                    return
                if action == "like" and current.reel and self._red_heart(target):
                    return
            self.sleep(0.3)
        message = (
            f"Instagram did not confirm {action}; the action will not be repeated."
        )
        raise PlatformError(message, result=Result(Status.UNCERTAIN, detail=message))

    def _show_post_buttons(self, view):
        try:
            identity = self.scroll.framed_post_identity(view.root)
            if not self.scroll.show_framed_post_row_of(identity, "like"):
                raise PlatformError("Cannot reveal the observed post's like control.")
            root = self.snapshot()
            if not identity or self.scroll.framed_post_identity(root) != identity:
                raise PlatformError(
                    "The post changed while revealing its like control."
                )
            revealed = read_post(root, self.width, self.height)
            if revealed.username.casefold() != view.username.casefold():
                raise PlatformError(
                    "The post changed while revealing its like control."
                )
            return revealed
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Cannot reveal the post's like control ({type(error).__name__})."
            ) from error

    def _red_heart(self, target):
        # Some reel viewers report selected=false even for a visibly liked heart.
        try:
            icon = self.phone.read("screenshot").crop(bounds(target)).convert("RGB")
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Cannot verify the reel's like state ({type(error).__name__})."
            ) from error
        icon.thumbnail((48, 48))
        red = sum(
            r > 170 and g < 100 and b < 150 for r, g, b in icon.get_flattened_data()
        )
        return red > icon.width * icon.height * 0.18

    def _unfollow_author(self, observation):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        self.open_profile(observation.username)
        try:
            root = self.snapshot()
            names = nodes(root, PROFILE_SELECTORS.username)
            if (
                len(names) != 1
                or text_of(names[0]).strip().casefold()
                != observation.username.casefold()
            ):
                raise PlatformError("The profile does not match the observed author.")
            buttons = nodes(root, PROFILE_SELECTORS.follow_button_anchors)
            if len(buttons) != 1:
                raise PlatformError("The profile's following control is unavailable.")
            label = text_of(buttons[0]).strip().lower()
            if label in ("follow", "follow back"):
                return
            if label != "following":
                raise PlatformError(
                    "The profile is not in a confirmed following state."
                )
            self.tap(buttons[0])
            self.sleep(0.5)
            self.tap_control([resource("follow_sheet_unfollow_row")])
            self.sleep(0.5)
            for _ in range(3):
                buttons = nodes(
                    self.snapshot(), PROFILE_SELECTORS.follow_button_anchors
                )
                if len(buttons) == 1 and text_of(buttons[0]).strip().lower() in (
                    "follow",
                    "follow back",
                ):
                    return
                self.sleep(0.5)
            self._unconfirmed("unfollow")
        finally:
            with self.phone.cleanup():
                self.phone.command("back").require()
                self.sleep(0.5)
                self._current(observation, allow_caption_change=True)

    def _close_save_sheet(self):
        for attempt in range(3):
            if not nodes(self.snapshot(), [resource("layout_container_bottom_sheet")]):
                return
            if attempt == 0:
                try:
                    self.phone.command("back").require()
                except PlatformError:
                    raise
                except Exception as error:
                    raise PlatformError(
                        f"Cannot close the save sheet ({type(error).__name__})."
                    ) from error
            self.sleep(0.5)
        raise PlatformError("The save sheet did not close.")

    def advance(self):
        self.expanded = False
        self._close_caption()
        if self.auto_advanced:
            self.auto_advanced = False
            return
        try:
            self.workflows[self.workflow].advance(self)
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Could not advance the workflow ({type(error).__name__})."
            ) from error

    def _close_caption(self):
        if self.caption_open:
            try:
                self.phone.command("back").require()
            except PlatformError:
                raise
            except Exception as error:
                raise PlatformError(
                    f"Cannot close the caption ({type(error).__name__})."
                ) from error
            self.sleep(0.4)
            self.caption_open = False
