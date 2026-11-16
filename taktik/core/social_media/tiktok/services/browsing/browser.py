import io
import re

from taktik.core.shared.browsing import ActionResult, PlatformError, PostObservation
from taktik.core.shared.phone_interaction import Phone, Result, Status
from taktik.core.shared.ui.geometry import bounds, nodes, text_of
from taktik.core.social_media.tiktok.ui.posts import (
    PACKAGE,
    caption_prefix,
    catalogs,
    excluded_content,
    photo_layout,
    read_photo_caption,
    read_post,
    same_post,
    unlabeled_for_you_card_bounds,
)


class TikTok:
    name = "tiktok"

    def __init__(self, phone, enabled_workflows):
        self.phone = phone
        self.sleep = lambda seconds: phone.wait(seconds, purpose="readiness")
        self.width, self.height = phone.read("size")
        self.enabled = set(enabled_workflows)
        if not self.enabled <= {"for_you", "search", "profile"}:
            raise ValueError("Unavailable TikTok workflow.")
        self.workflow = "for_you"
        self.expanded = False
        self.caption_open = False

    def start_current_account(self):
        self.phone.command("launch", PACKAGE).require()
        self.sleep(1)
        self.go_tab("profile_tab")
        return self._profile_handle()

    @classmethod
    def connect(cls, serial, enabled_workflows):
        return cls(Phone.connect(serial), enabled_workflows)

    def go_tab(self, name):
        from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import (
            NAVIGATION_SELECTORS,
        )

        selectors = getattr(NAVIGATION_SELECTORS, name)
        for _ in range(5):
            choices = nodes(self.snapshot(), selectors, (0, 0, self.width, self.height))
            if len(choices) == 1:
                if choices[0].get("selected") != "true":
                    self.tap(choices[0])
                    self.sleep(0.5)
                return
            self.phone.command("back").require()
            self.sleep(0.4)
        raise PlatformError("Cannot reach the TikTok navigation tab.")

    def snapshot(self):
        from taktik.core.shared.device.snapshot import ScreenSnapshot

        try:
            root = ScreenSnapshot(self.phone.read("hierarchy")).root
            if not any(
                n.get("package") == PACKAGE
                and bounds(n)
                and (bounds(n)[2] - bounds(n)[0]) * (bounds(n)[3] - bounds(n)[1])
                >= self.width * self.height * 0.5
                for n in root.iter()
            ):
                raise PlatformError("TikTok is not the foreground app.")
            return root
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Cannot read TikTok's screen ({type(error).__name__})."
            ) from error

    def tap(self, node):
        self.phone.tap(bounds(node)).require()

    def _one(self, root, selectors):
        choices = nodes(root, selectors, (0, 0, self.width, self.height))
        if len(choices) != 1:
            raise PlatformError("The TikTok control is missing or ambiguous.")
        return choices[0]

    def _position(self, view):
        previous = getattr(self, "photo_position", None)
        if view.media_type == "photo":
            if (
                view.slide_index is None
                and previous
                and previous.identity == view.identity
            ):
                view.slide_index, view.slide_count = (
                    previous.slide_index,
                    previous.slide_count,
                )
            if view.slide_index is not None:
                self.photo_position = view
        else:
            self.photo_position = None
        return view

    def _read(self, root):
        reference = getattr(self, "caption_reference", None)
        if (
            reference
            and reference.media_type == "photo"
            and nodes(root, ['//*[@resource-id="com.zhiliaoapp.musically:id/snd"]'])
        ):
            return read_photo_caption(root, reference, self.width, self.height)
        return self._position(read_post(root, self.width, self.height))

    def _view(self):
        return self._read(self.snapshot())

    def viewing_screen(self):
        from taktik.core.social_media.tiktok.ui.selectors.shell.popups import (
            POPUP_SELECTORS,
        )

        root = self.snapshot()
        if nodes(root, POPUP_SELECTORS.suggestion_page_indicator):
            return "suggestion", {}
        creator, engagement, media, _, state = catalogs()
        if nodes(root, state.live_preview):
            return "live", {}
        if nodes(root, state.ad_label):
            description = " ".join(
                text_of(n) for n in nodes(root, media.video_description)
            )
            author = " ".join(text_of(n) for n in nodes(root, creator.author_username))
            return "ad", {
                "identity": "ad:" + author + description,
                "description": description,
            }
        if excluded_content(root, self.width, self.height) or self._survey(root)[0]:
            return "manual", {}
        view = self._read(root)
        hearts = nodes(root, engagement.like_button + state.unlike_indicator)
        return "post", {
            "identity": view.identity,
            "description": view.caption,
            "is_liked": len(hearts) == 1 and self._engaged(hearts[0], "like"),
            "like_count": view.like_count,
        }

    def _prime_photo(self):
        # The numeric photo badge fades; read it immediately after navigation.
        try:
            self._view()
        except PlatformError:
            pass

    def _current(self, observation, *, expanded=False):
        view = self._view()
        if observation.excluded or not same_post(
            view, observation, expanded=expanded or observation.caption_expanded
        ):
            raise PlatformError("The TikTok post changed before the action.")
        if view.media_type == "photo" and view.slide_index is None:
            view.slide_index, view.slide_count = (
                observation.slide_index,
                observation.slide_count,
            )
        return view

    def _profile_handle(self):
        from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        root = self.snapshot()
        for _ in range(2):
            if nodes(root, PROFILE_SELECTORS.username):
                break
            if not nodes(root, PROFILE_SELECTORS.videos_tab):
                raise PlatformError("The expected TikTok profile is not visible.")
            self.phone.gesture(
                "scroll",
                "down",
                (0, self.height * 0.15, self.width * 0.8, self.height * 0.85),
                distance=self.height * 0.4,
            ).require()
            self.sleep(0.5)
            root = self.snapshot()
        node = self._one(root, PROFILE_SELECTORS.username)
        handle = text_of(node).strip().removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", handle):
            raise PlatformError("Cannot verify the TikTok profile handle.")
        return handle

    def start(self, username, workflow, target=""):
        try:
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
            if self._profile_handle().casefold() != username.casefold():
                raise PlatformError(
                    "The active TikTok handle does not match the configured account mapping."
                )
            self.transition(workflow, target)
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"TikTok startup failed ({type(error).__name__})."
            ) from error

    def transition(self, workflow, target=""):
        from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import (
            NAVIGATION_SELECTORS,
        )

        if workflow not in self.enabled:
            raise PlatformError("The requested workflow is disabled.")
        self._close_caption()
        try:
            if workflow == "for_you":
                self.go_tab("home_tab")
                tab = self._one(self.snapshot(), NAVIGATION_SELECTORS.for_you_tab)
                if tab.get("selected") != "true":
                    self.tap(tab)
            elif workflow == "search":
                self._search_results(target)
                from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import (
                    SEARCH_SELECTORS,
                )

                self.tap(self._one(self.snapshot(), SEARCH_SELECTORS.top_tab))
                selectors = (
                    SEARCH_SELECTORS.video_result_cell
                    + SEARCH_SELECTORS.video_result_container
                )
                self._open_result(selectors)
                for _ in range(6):
                    root = self.snapshot()
                    if not nodes(root, selectors):
                        break
                    self.sleep(0.4)
                else:
                    self._open_result(selectors)
                root = self.snapshot()
                if nodes(root, SEARCH_SELECTORS.results_page + selectors):
                    raise PlatformError(
                        "TikTok did not open a post from search results."
                    )
                if not excluded_content(root, self.width, self.height):
                    self._read(root)
            elif workflow == "profile":
                # Only startup can supply a handle. Model author visits use visit_author.
                if not re.fullmatch(r"[A-Za-z0-9_.]{1,30}", target):
                    raise PlatformError(
                        "Starting profile browsing requires an exact handle."
                    )
                from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import (
                    SEARCH_SELECTORS,
                )

                self._search_results(target)
                self.tap(self._one(self.snapshot(), SEARCH_SELECTORS.users_tab))
                self._open_result(
                    SEARCH_SELECTORS.user_result_selectors_for_username(target)
                )
                if self._profile_handle().casefold() != target.casefold():
                    raise PlatformError("Cannot verify the requested TikTok profile.")
                self._open_profile_post()
            else:
                raise PlatformError("Unavailable TikTok workflow.")
            self.workflow = workflow
            self._prime_photo()
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"TikTok navigation failed ({type(error).__name__})."
            ) from error

    def _search_results(self, query):
        from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import (
            NAVIGATION_SELECTORS,
        )
        from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import (
            SEARCH_SELECTORS,
        )

        if not query.strip():
            raise PlatformError("Search needs a nonempty query.")
        self.go_tab("home_tab")
        # The English 47.0.3 header magnifier has no accessibility label.
        search = NAVIGATION_SELECTORS.search_button + [
            '//*[@resource-id="com.zhiliaoapp.musically:id/k_8"]'
        ]
        self.tap(self._one(self.snapshot(), search))
        field = self._one(self.snapshot(), SEARCH_SELECTORS.search_input)
        resource_id = field.get("resource-id")
        if not resource_id:
            raise PlatformError(
                "The TikTok search field has no stable control identifier."
            )
        self.phone.enter_text(
            resource_id,
            query,
            submit=lambda: self.tap(
                self._one(self.snapshot(), SEARCH_SELECTORS.search_submit_button)
            ),
        ).require()

    def _open_result(self, selectors):
        for _ in range(8):
            results = nodes(self.snapshot(), selectors, (0, 0, self.width, self.height))
            if results:
                self.tap(results[0])
                self._prime_photo()
                return
            self.sleep(0.5)
        raise PlatformError("No TikTok search result could be opened.")

    def _open_profile_post(self):
        from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        tiles = nodes(
            self.snapshot(),
            PROFILE_SELECTORS.video_item,
            (0, 0, self.width, self.height),
        )
        if not tiles:
            raise PlatformError("No TikTok profile posts could be opened.")
        self.tap(tiles[0])
        self._view()

    def _open_author(self, observation):
        self._close_caption()
        view = self._current(observation, expanded=True)
        # Tap the name text, never the avatar with its overlapping Follow button.
        creator, *_ = catalogs()
        excluded = [
            bounds(button) for button in nodes(view.root, creator.follow_button)
        ]
        self.phone.tap(bounds(view.author), exclude=excluded).require()
        return self._profile_handle()

    def visit_author(self, observation):
        if "profile" not in self.enabled:
            raise PlatformError("The profile workflow is disabled.")
        try:
            self._open_author(observation)
            self._open_profile_post()
            self.workflow = "profile"
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Cannot visit the observed author ({type(error).__name__})."
            ) from error

    def _survey(self, root):
        headings = {
            "Is this video appropriate for TikTok?": "question",
            "It's because this video is": "reason",
        }
        panels = []
        for panel in nodes(
            root,
            [
                (
                    f'//*[@package="{PACKAGE}"]'
                    '[@class="androidx.compose.ui.platform.ComposeView"'
                    " or self::androidx.compose.ui.platform.ComposeView]/*"
                )
            ],
            (0, 0, self.width, self.height),
        ):
            for child in panel:
                if text_of(child) in headings:
                    panels.append((headings[text_of(child)], panel))
        if len(panels) > 1:
            raise PlatformError("The TikTok appropriateness survey is ambiguous.")
        return panels[0] if panels else (None, None)

    def _survey_buttons(self, panel, label):
        if panel is None:
            return []
        return nodes(
            panel,
            [
                (
                    f'.//*[@text="{label}"]/parent::*'
                    f'[@package="{PACKAGE}"][@clickable="true"]'
                )
            ],
            bounds(panel),
        )

    def _survey_click(self, panel, label, ready):
        buttons = self._survey_buttons(panel, label)
        if len(buttons) != 1:
            raise PlatformError(f"TikTok survey requires one enabled {label} button.")
        self.tap(buttons[0])
        for _ in range(6):
            root = self.snapshot()
            stage, panel = self._survey(root)
            if ready(stage, panel):
                return root
            self.sleep(0.3)
        raise PlatformError(f"TikTok survey did not respond to {label}.")

    def _answer_survey(self, root):
        if self.workflow != "for_you":
            return root
        stage, panel = self._survey(root)
        if stage == "question":
            for label in ("No", "Yes but only for over 18's"):
                if len(self._survey_buttons(panel, label)) != 1:
                    raise PlatformError("Unrecognized TikTok appropriateness survey.")
            root = self._survey_click(
                panel, "Yes", lambda stage, _: stage != "question"
            )
            stage, panel = self._survey(root)
        if stage == "reason":
            reasons = []
            for label in (
                "Entertaining",
                "Useful",
                "Educational",
                "Relatable",
                "Other",
            ):
                buttons = self._survey_buttons(panel, label)
                if len(buttons) != 1:
                    raise PlatformError("Unrecognized TikTok survey reasons.")
                reasons.append((bounds(buttons[0])[1], bounds(buttons[0])[0], label))
            if not self._survey_buttons(panel, "Submit"):
                root = self._survey_click(
                    panel,
                    min(reasons)[2],
                    lambda stage, panel: (
                        stage == "reason"
                        and len(self._survey_buttons(panel, "Submit")) == 1
                    ),
                )
                _, panel = self._survey(root)
            root = self._survey_click(panel, "Submit", lambda stage, _: stage is None)
        return root

    def observe(self, frame_count, interval, previous=None):
        try:
            root = self._answer_survey(self.snapshot())
            if excluded_content(root, self.width, self.height):
                if previous:
                    raise PlatformError("The TikTok post changed during inspection.")
                return PostObservation(
                    "", "", "excluded", self.workflow, platform=self.name, excluded=True
                )
            view = self._read(root)
            if previous and not same_post(
                view, previous, expanded=self.expanded or previous.caption_expanded
            ):
                raise PlatformError("The TikTok post changed during inspection.")
            caption = view.caption
            if (
                previous
                and previous.caption_expanded
                and len(previous.caption) > len(caption)
            ):
                caption = previous.caption
            if previous and view.media_type == "photo" and view.slide_index is None:
                view.slide_index, view.slide_count = (
                    previous.slide_index,
                    previous.slide_count,
                )
                self.photo_position = view
            frames = list(previous.frames) if previous else []
            for index in range(
                1 if view.media_type == "photo" else min(frame_count, 6)
            ):
                if index:
                    self.phone.wait(interval, purpose="frame")
                image = self.phone.read("screenshot").crop(view.crop).convert("RGB")
                image.thumbnail((1024, 1024))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=80)
                frames.append(buffer.getvalue())
            after = self._view()
            if after.identity != view.identity or after.slide_index != view.slide_index:
                raise PlatformError("The TikTok post changed during frame capture.")
            self.expanded = False
            return PostObservation(
                view.username,
                caption,
                previous.identity if previous else view.identity,
                self.workflow,
                frames[-6:],
                view.visible_text,
                caption_expanded=bool(previous and previous.caption_expanded),
                like_count=previous.like_count if previous else view.like_count,
                post_time=(previous.post_time or view.post_time)
                if previous
                else view.post_time,
                platform=self.name,
                media_type=view.media_type,
                slide_index=view.slide_index,
                slide_count=view.slide_count,
                source_key=view.source_key,
                date_label=view.date_label,
                caption_type=previous.caption_type
                if previous and caption == previous.caption and caption != view.caption
                else view.caption_type,
            )
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"TikTok capture failed ({type(error).__name__})."
            ) from error

    def read_more(self, observation):
        view = self._current(observation)
        if caption_prefix(view.caption) == view.caption:
            return
        _, _, media, *_ = catalogs()
        caption = self._one(view.root, media.video_description)
        # TikTok's ellipsis is at the end of the last line; the centre can be a hashtag.
        left, top, right, bottom = bounds(caption)
        try:
            self.caption_reference = observation
            self.phone.tap(
                (
                    right - min((right - left) * 0.2, self.width * 0.1),
                    bottom - min(40, (bottom - top) / 2),
                    right,
                    bottom,
                )
            ).require()
            self.caption_open = True
            self.sleep(0.5)
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Could not expand TikTok caption ({type(error).__name__})."
            ) from error
        after = self._current(observation, expanded=True)
        if after.caption == view.caption:
            self.caption_open = False
            self.caption_reference = None
            raise PlatformError("TikTok did not expand the caption.")
        self.expanded = True
        self.caption_open = True

    def inspect(self, observation):
        self._close_caption()
        view = self._current(observation, expanded=True)
        if view.media_type != "photo" or view.slide_index is None:
            raise PlatformError("Cannot verify a TikTok photo slide counter.")
        if view.slide_index >= view.slide_count:
            return
        layout = photo_layout(view.root, view.crop)
        region = view.crop
        if layout.images:
            # A horizontal page can show the next slide at the edge of the pager.
            # Use their shared image band, clipped above the pagination controls.
            left = min(rect[0] for rect in layout.images)
            right = max(rect[2] for rect in layout.images)
            top = max(rect[1] for rect in layout.images)
            bottom = min(
                [rect[3] for rect in layout.images]
                + [rect[1] for rect in layout.controls]
            )
            if top >= bottom:
                raise PlatformError("No shared image band for horizontal paging.")
            region = (left, top, right, bottom)
        self.phone.gesture("horizontal", "left", region).require()
        self.sleep(0.5)
        after = self._current(observation, expanded=True)
        if (
            after.slide_count != view.slide_count
            or after.slide_index != view.slide_index + 1
        ):
            raise PlatformError("TikTok did not advance exactly one photo slide.")

    def _close_caption(self):
        if self.caption_open:
            try:
                collapse = nodes(
                    self.snapshot(),
                    ['//*[contains(@resource-id, ":id/tv_toggle")][@text="less"]'],
                )
                if len(collapse) == 1:
                    self.tap(collapse[0])
                else:
                    self.phone.command("back").require()
                    self.sleep(0.4)
            except PlatformError:
                raise
            except Exception as error:
                raise PlatformError(
                    f"Cannot close the TikTok caption ({type(error).__name__})."
                ) from error
            self.caption_open = False
            self.caption_reference = None
        self.expanded = False

    def advance(self):
        try:
            self._close_caption()
            self.photo_position = None
            root = self.snapshot()
            _, _, media, *_ = catalogs()
            area = (0, 0, self.width, self.height)
            containers = nodes(root, media.video_container, area)
            fallback = (
                bounds(containers[0])
                if len(containers) == 1
                else unlabeled_for_you_card_bounds(root, self.width, self.height)
            )
            layout = photo_layout(root, fallback or area)
            left, top, right, bottom = (
                layout.swipe_bounds(fallback) if layout.detected else fallback or area
            )
            # Keep the stroke above photo controls and clear of the action rail.
            region = (left, top, min(right, self.width * 0.8), bottom)
            self.phone.gesture("page", "up", region).require()
            self.sleep(0.7)
            self._prime_photo()
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"Could not advance TikTok ({type(error).__name__})."
            ) from error

    @staticmethod
    def _engaged(button, action):
        label = button.get("content-desc", "").casefold()
        if action == "like" and (label.startswith(("unlike", "liked"))):
            return True
        if action == "save" and label.startswith("remove from favour"):
            return True
        if action == "save" and label.startswith("remove from favor"):
            return True
        if any(
            n.get("selected") == "true" or n.get("checked") == "true"
            for n in button.iter()
        ):
            return True
        invitation = (
            label.startswith("like video")
            if action == "like"
            else label.startswith(
                (
                    "add to favor",
                    "add to favour",
                    "add or remove this video from favor",
                    "add or remove this video from favour",
                )
            )
        )
        if invitation and any(n.get("selected") == "false" for n in button.iter()):
            return False
        raise PlatformError("TikTok's current engagement state is not verifiable.")

    def _toggle(self, action, observation):
        _, engagement, _, _, state = catalogs()
        selectors = (
            (
                engagement.like_button
                + state.unlike_indicator
                + state.video_already_liked
            )
            if action == "like"
            else (
                engagement.favorite_button
                + [
                    '//*[starts-with(@content-desc, "Add or remove this video from Favorites") or starts-with(@content-desc, "Remove from Favorites") or starts-with(@content-desc, "Remove from Favourites")]'
                ]
            )
        )
        view = self._current(observation, expanded=True)
        button = self._one(view.root, selectors)
        if self._engaged(button, action):
            return
        self.tap(button)
        for _ in range(3):
            current = self._current(observation, expanded=True)
            if self._engaged(self._one(current.root, selectors), action):
                return
            self.sleep(0.4)
        message = "TikTok did not confirm the engagement action."
        raise PlatformError(message, result=Result(Status.UNCERTAIN, detail=message))

    @staticmethod
    def _profile_button_selectors(selectors, labels):
        predicate = " or ".join(
            f'normalize-space(@text)="{label}" or normalize-space(@content-desc)="{label}"'
            for label in labels
        )
        return [
            selector + f"[{predicate}]"
            for selector in [
                *selectors,
                '//*[@resource-id="com.zhiliaoapp.musically:id/fmp"]',
                '//*[@clickable="true"]',
            ]
        ]

    def _follow(self, action, observation):
        from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        follow_selectors = self._profile_button_selectors(
            PROFILE_SELECTORS.follow_button, ("Follow", "Follow back")
        )
        following_selectors = self._profile_button_selectors(
            PROFILE_SELECTORS.following_button, ("Following", "Friends")
        )
        handle = self._open_author(observation)
        try:
            root = self.snapshot()
            following = nodes(root, following_selectors)
            follow = nodes(root, follow_selectors)
            if following:
                if action == "follow":
                    return
                self.tap(self._one(root, following_selectors))
                confirmation = nodes(
                    self.snapshot(),
                    ['//*[@text="Unfollow"]', '//*[@content-desc="Unfollow"]'],
                )
                if confirmation:
                    self.tap(
                        self._one(
                            self.snapshot(),
                            ['//*[@text="Unfollow"]', '//*[@content-desc="Unfollow"]'],
                        )
                    )
            else:
                if len(follow) != 1 or text_of(follow[0]).strip() not in (
                    "Follow",
                    "Follow back",
                ):
                    raise PlatformError("Cannot verify the author's follow state.")
                if action == "unfollow":
                    return
                self.tap(follow[0])
            if self._profile_handle().casefold() != handle.casefold():
                raise PlatformError("The author profile changed during engagement.")
            expected = following_selectors if action == "follow" else follow_selectors
            button = self._one(self.snapshot(), expected)
            if action == "unfollow" and text_of(button).strip() not in (
                "Follow",
                "Follow back",
            ):
                raise PlatformError("TikTok did not confirm Unfollow.")
        finally:
            with self.phone.cleanup():
                for attempt in range(3):
                    self.phone.command("back").require()
                    self.sleep(0.5)
                    try:
                        self._current(observation, expanded=True)
                        break
                    except PlatformError:
                        if attempt == 2:
                            raise

    def _not_interested(self, observation):
        _, engagement, _, share, _ = catalogs()
        view = self._current(observation, expanded=True)
        self.tap(self._one(view.root, engagement.share_button))
        sheet_open = True
        try:
            root = self.snapshot()
            sheet = self._one(root, share.sheet_indicator)
            choices = nodes(root, share.not_interested_button, bounds(sheet))
            if not choices:
                self.phone.command("back").require()
                self.sleep(0.4)
                view = self._current(observation, expanded=True)
                left, top, right, bottom = view.crop
                self.phone.tap(
                    (
                        left + (right - left) * 0.25,
                        top + (bottom - top) * 0.25,
                        left + (right - left) * 0.55,
                        top + (bottom - top) * 0.55,
                    ),
                    kind="long_press",
                ).require()
                self.sleep(0.5)
                root = self.snapshot()
                sheets = nodes(root, share.sheet_indicator)
                choices = (
                    nodes(root, share.not_interested_button, bounds(sheets[0]))
                    if len(sheets) == 1
                    else []
                )
            if len(choices) != 1:
                raise PlatformError(
                    "The feedback sheet offers no unambiguous Not interested control."
                )
            self.tap(choices[0])
            for _ in range(4):
                root = self.snapshot()
                if not nodes(root, share.sheet_indicator):
                    sheet_open = False
                    if excluded_content(root, self.width, self.height):
                        return ActionResult(advanced=True)
                    after = read_post(root, self.width, self.height)
                    if not same_post(after, observation, expanded=True):
                        return ActionResult(advanced=True)
                self.sleep(0.5)
            message = "TikTok did not confirm advancement after Not interested."
            raise PlatformError(
                message, result=Result(Status.UNCERTAIN, detail=message)
            )
        finally:
            with self.phone.cleanup():
                if sheet_open and nodes(self.snapshot(), share.sheet_indicator):
                    self.phone.command("back").require()
                    self.sleep(0.4)

    def act(self, action, observation):
        try:
            self._current(observation)
            if action in ("skip", "watch"):
                return ActionResult()
            self._close_caption()
            if action in ("like", "save"):
                self._toggle(action, observation)
            elif action in ("follow", "unfollow"):
                self._follow(action, observation)
            elif action == "not_interested":
                return self._not_interested(observation)
            else:
                raise PlatformError("Unsupported TikTok action.")
            return ActionResult()
        except PlatformError:
            raise
        except Exception as error:
            raise PlatformError(
                f"TikTok action failed ({type(error).__name__})."
            ) from error
