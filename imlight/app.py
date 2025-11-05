from slimgui.integrations.glfw import GlfwRenderer
from typing import List, Any, Tuple
from slimgui import imgui

from .fixture import ActiveFixture, DMXUniverse, DRIVERS
from .fixture.all import ALL_FIXTURES
from .window import TexturedWindow, Window, ImguiAboutWindow


class UniversesWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Universes")
        self.app = app
        self.drivers = [driver.clean_name for driver in DRIVERS]
        self.drivers.append("None")

    def pre_draw(self):
        imgui.set_next_window_size((560, 130), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((10, 30), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        if imgui.button("Add New Universe"):
            self.app.universes.append(DMXUniverse())

        imgui.separator()

        if imgui.begin_table("universes", 4, flags=imgui.TableFlags.BORDERS):
            imgui.table_setup_column("ID")
            imgui.table_setup_column("Driver")
            imgui.table_setup_column("Fixtures")
            imgui.table_setup_column("Actions")
            imgui.table_headers_row()

            universe_to_remove_index = None

            for i, universe in enumerate(self.app.universes):
                imgui.table_next_row()

                imgui.table_next_column()
                imgui.text(str(i))

                imgui.table_next_column()
                selected_idx = self.drivers.index(
                    "None"
                    if universe.driver is None
                    else universe.driver.__class__.clean_name
                )
                changed, new_idx = imgui.combo(
                    f"##driver_combo_{i}", selected_idx, self.drivers
                )
                if changed:
                    if self.drivers[new_idx] == "None":
                        universe.driver = None
                    else:
                        universe.driver = DRIVERS[new_idx]()

                imgui.table_next_column()
                imgui.text(str(len(universe.fixtures)))

                imgui.table_next_column()

                # TODO: add button to configure driver
                if imgui.button(f"Remove##{i}"):
                    universe_to_remove_index = i

            imgui.end_table()

            if universe_to_remove_index is not None:
                removed_universe = self.app.universes.pop(universe_to_remove_index)
                fixtures_to_deselect = [
                    f
                    for f in self.app.selected_fixtures
                    if f in removed_universe.fixtures
                ]
                for f in fixtures_to_deselect:
                    self.app.selected_fixtures.remove(f)


class PatchWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Patch")
        self.app = app

        self.fixture_profiles = ALL_FIXTURES
        self.fixture_names = [
            f"{f.manufacturer} - {f.model}" for f in self.fixture_profiles
        ]

        self.selected_universe_index: int = 0
        self.selected_fixture_index: int = 0
        self.start_address: int = 1
        self.fixture_count: int = 1

        self.status_message: str = ""  # type: ignore
        self.status_is_error: bool = False  # type: ignore
        self.initial_x, self.initial_y = 30, 30
        self.spacing = 20

    def next_position(self):
        self.initial_x += self.spacing
        # if self.initial_x >

    def pre_draw(self):
        imgui.set_next_window_size((560, 990), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((10, 170), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        imgui.text("Add New Fixture(s)")
        imgui.separator()

        if not self.app.universes:
            imgui.text_colored(
                (1, 1, 1, 1), "Please add a universe in the 'Universes' window first."
            )
            return

        self.selected_universe_index = min(
            self.selected_universe_index, len(self.app.universes) - 1
        )

        universe_names = [f"Universe {i + 1}" for i in range(len(self.app.universes))]
        changed, self.selected_universe_index = imgui.combo(
            "Target Universe", self.selected_universe_index, universe_names
        )

        changed, self.selected_fixture_index = imgui.combo(
            "Fixture Type", self.selected_fixture_index, self.fixture_names
        )

        changed, self.start_address = imgui.input_int(
            "Start Address", self.start_address
        )
        self.start_address = max(1, self.start_address)

        changed, self.fixture_count = imgui.input_int("Count", self.fixture_count)
        self.fixture_count = max(1, self.fixture_count)

        imgui.spacing()

        if imgui.button("Patch Fixtures"):
            self.patch_fixtures()

        if self.status_message:
            color = (1, 0, 0, 1) if self.status_is_error else (0, 1, 0, 1)
            imgui.text_colored(color, self.status_message)

        imgui.separator()
        imgui.text("Patched Fixtures")

        if imgui.begin_child("patched_fixtures_list"):
            target_universe = self.app.universes[self.selected_universe_index]
            fixture_to_remove = None

            if imgui.begin_table("patched_list", 4, flags=imgui.TableFlags.BORDERS):
                imgui.table_setup_column(
                    "Addr",
                    flags=imgui.TableColumnFlags.WIDTH_FIXED,
                    init_width_or_weight=40,
                )
                imgui.table_setup_column(
                    "Name",
                    flags=imgui.TableColumnFlags.WIDTH_STRETCH,
                    init_width_or_weight=2,
                )
                imgui.table_setup_column(
                    "Channels",
                    flags=imgui.TableColumnFlags.WIDTH_FIXED,
                    init_width_or_weight=65,
                )
                imgui.table_setup_column(
                    "Actions",
                    flags=imgui.TableColumnFlags.WIDTH_FIXED,
                    init_width_or_weight=60,
                )
                imgui.table_headers_row()

                for fixture in target_universe.fixtures:
                    imgui.table_next_row()
                    imgui.table_next_column()

                    is_selected = fixture in self.app.selected_fixtures

                    changed, _ = imgui.selectable(
                        f"{fixture.start_address}##{fixture.start_address}",
                        is_selected,
                        flags=imgui.SelectableFlags.SPAN_ALL_COLUMNS,
                    )

                    if changed:
                        io = imgui.get_io()
                        if io.key_ctrl:  # Ctrl-click to toggle
                            if is_selected:
                                self.app.selected_fixtures.remove(fixture)
                            else:
                                self.app.selected_fixtures.append(fixture)
                        else:  # Simple click to select only one
                            self.app.selected_fixtures.clear()
                            if not is_selected:
                                self.app.selected_fixtures.append(fixture)

                    imgui.table_next_column()
                    imgui.text(fixture.profile.model)
                    imgui.table_next_column()
                    imgui.text(str(fixture.profile.channel_count))
                    imgui.table_next_column()

                    if imgui.button(f"Remove##{fixture.start_address}"):
                        fixture_to_remove = fixture

                imgui.end_table()

            if fixture_to_remove is not None:
                target_universe.fixtures.remove(fixture_to_remove)
                if fixture_to_remove in self.app.selected_fixtures:
                    self.app.selected_fixtures.remove(fixture_to_remove)
                self.status_message = "Removed fixture!"
                self.status_is_error = False

            imgui.end_child()

    def patch_fixtures(self):
        """The core logic for adding fixtures to the selected universe."""
        try:
            target_universe = self.app.universes[self.selected_universe_index]
            fixture_profile = self.fixture_profiles[self.selected_fixture_index]

            current_address = self.start_address

            for i in range(self.fixture_count):
                fixture_to_add = ActiveFixture(
                    profile=fixture_profile,
                    start_address=current_address,
                    start_stagepos=(0.05 + i * 0.03, 0.05 + i * 0.03),
                )

                target_universe.add_fixture(fixture_to_add)

                current_address += fixture_profile.channel_count

            self.status_message = (
                f"Successfully patched {self.fixture_count} fixture(s)."
            )
            self.status_is_error = False

            self.start_address = current_address

        except IndexError:
            self.status_message = "Error: Invalid universe or fixture selected."
            self.status_is_error = True
        except ValueError as e:
            self.status_message = f"Error: {e}"
            self.status_is_error = True


class GridviewWindow(Window):
    """
    A window that displays a compact grid of all patched fixtures.
    Detailed information is available via tooltips.
    """

    def __init__(self, app: "App"):
        super().__init__("Gridview")
        self.app = app
        self.is_open = True

        self.is_drag_selecting = False
        self.drag_start_pos = (0, 0)
        self.fixtures_in_drag_rect = set()

    def pre_draw(self):
        imgui.set_next_window_pos((580, 30), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((780, 480), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        """Draws the grid of all fixtures across all universes."""
        io = imgui.get_io()

        if (
            imgui.is_window_hovered()
            and io.key_ctrl
            and imgui.is_mouse_clicked(imgui.MouseButton.LEFT)
        ):
            self.is_drag_selecting = True
            self.drag_start_pos = io.mouse_pos
            self.fixtures_in_drag_rect.clear()

        if self.is_drag_selecting and imgui.is_mouse_released(imgui.MouseButton.LEFT):
            current_selection_set = set(self.app.selected_fixtures)
            final_selection_set = current_selection_set.union(
                self.fixtures_in_drag_rect
            )
            self.app.selected_fixtures = list(final_selection_set)

            self.is_drag_selecting = False
            self.fixtures_in_drag_rect.clear()

        if self.is_drag_selecting:
            self.fixtures_in_drag_rect.clear()

        tile_size = 60
        tile_spacing = 4
        available_width = imgui.get_content_region_avail()[0]
        num_columns = max(1, int(available_width / (tile_size + tile_spacing)))

        window_draw_list = imgui.get_window_draw_list()
        window_draw_list.channels_split(2)

        imgui.columns(num_columns, "fixture_grid", border=False)

        for universe in self.app.universes:
            for fixture in universe.fixtures:
                window_draw_list.channels_set_current(0)

                self._draw_fixture_tile_content(fixture, tile_size)

                if self.is_drag_selecting:
                    min_rect = imgui.get_item_rect_min()
                    max_rect = imgui.get_item_rect_max()

                    drag_rect_min_x = min(self.drag_start_pos[0], io.mouse_pos[0])
                    drag_rect_min_y = min(self.drag_start_pos[1], io.mouse_pos[1])
                    drag_rect_max_x = max(self.drag_start_pos[0], io.mouse_pos[0])
                    drag_rect_max_y = max(self.drag_start_pos[1], io.mouse_pos[1])

                    if (
                        max_rect[0] >= drag_rect_min_x
                        and min_rect[0] <= drag_rect_max_x
                        and max_rect[1] >= drag_rect_min_y
                        and min_rect[1] <= drag_rect_max_y
                    ):
                        self.fixtures_in_drag_rect.add(fixture)

                window_draw_list.channels_set_current(1)
                self._draw_fixture_tile_overlay(fixture)

                imgui.next_column()

        imgui.columns(1)

        if self.is_drag_selecting:
            window_draw_list.channels_set_current(1)

            rect_color = imgui.get_color_u32((0.2, 0.4, 1.0, 0.25))
            border_color = imgui.get_color_u32((0.4, 0.6, 1.0, 0.8))
            window_draw_list.add_rect_filled(
                self.drag_start_pos, io.mouse_pos, rect_color
            )
            window_draw_list.add_rect(
                self.drag_start_pos, io.mouse_pos, border_color, thickness=1.0
            )

        window_draw_list.channels_merge()

    def _get_fixture_color(
        self, fixture: ActiveFixture
    ) -> Tuple[float, float, float, float]:
        r, g, b = 0.0, 0.0, 0.0
        has_color = False
        if "red" in fixture.profile.channel_map:
            r = fixture.red / 255.0
            has_color = True  # type: ignore
        if "green" in fixture.profile.channel_map:
            g = fixture.green / 255.0
            has_color = True  # type: ignore
        if "blue" in fixture.profile.channel_map:
            b = fixture.blue / 255.0
            has_color = True  # type: ignore
        intensity = 1.0
        if "intensity" in fixture.profile.channel_map:
            intensity = fixture.intensity / 255.0  # type: ignore
        if has_color:
            return (r * intensity, g * intensity, b * intensity, 1.0)
        else:
            return (intensity, intensity, intensity, 1.0)

    def _draw_fixture_tile_content(self, fixture: ActiveFixture, size: float):
        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, (0, 0))
        imgui.begin_child(f"fixture_{fixture.start_address}", size=(size, size))

        draw_list = imgui.get_window_draw_list()
        start_pos = imgui.get_cursor_screen_pos()
        end_pos = (start_pos[0] + size, start_pos[1] + size)
        color = self._get_fixture_color(fixture)
        draw_list.add_rect_filled(start_pos, end_pos, imgui.get_color_u32(color))

        imgui.set_cursor_screen_pos(start_pos)

        if (
            imgui.invisible_button(f"##tile_{fixture.start_address}", (size, size))
            and not self.is_drag_selecting
        ):
            io = imgui.get_io()
            is_selected = fixture in self.app.selected_fixtures
            if io.key_ctrl:
                if is_selected:
                    self.app.selected_fixtures.remove(fixture)
                else:
                    self.app.selected_fixtures.append(fixture)
            else:
                self.app.selected_fixtures.clear()
                if not is_selected:
                    self.app.selected_fixtures.append(fixture)

        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        text_color = (
            imgui.get_color_u32((1, 1, 1, 1))
            if luminance < 0.5
            else imgui.get_color_u32((0, 0, 0, 1))
        )
        text = f"@{fixture.start_address}"
        padding = 4
        draw_list.add_text(
            (start_pos[0] + padding, start_pos[1] + padding), text_color, text
        )

        imgui.end_child()
        imgui.pop_style_var()

    def _draw_fixture_tile_overlay(self, fixture: ActiveFixture):
        is_selected = (
            fixture in self.app.selected_fixtures
            or fixture in self.fixtures_in_drag_rect
        )

        if is_selected:
            min_rect = imgui.get_item_rect_min()
            max_rect = imgui.get_item_rect_max()
            draw_list = imgui.get_window_draw_list()
            draw_list.add_rect(
                min_rect, max_rect, imgui.get_color_u32((1, 1, 0, 1)), thickness=2
            )

        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text(fixture.name)
            imgui.separator()
            intensity_percent = (
                (fixture.intensity / 255.0)
                if "intensity" in fixture.profile.channel_map
                else 1.0
            )  # type: ignore
            imgui.text(f"Intensity: {intensity_percent:.0%}")
            imgui.end_tooltip()


class StageviewWindow(TexturedWindow):
    """
    This window demonstrates the aspect lock and background texture.
    It has a 16:9 aspect ratio and loads 'my_background.png'.
    """

    def __init__(self, app: "App"):
        super().__init__(
            title="Stageview", aspect_ratio=2500 / 2658, image_path="stage.png"
        )
        self.app = app
        self.is_open = True
        self.dragged_fixture_start_pos: dict[ActiveFixture, Tuple[float, float]] = {}

    def pre_draw(self):
        super().pre_draw()
        imgui.set_next_window_pos((1370, 30), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((598, 635), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        draw_list = imgui.get_window_draw_list()
        window_pos = imgui.get_window_pos()
        window_size = imgui.get_window_size()
        io = imgui.get_io()

        fixture_radius = 10

        for universe in self.app.universes:
            for fixture in universe.fixtures:
                center_x = window_pos[0] + fixture.stagepos[0] * window_size[0]
                center_y = window_pos[1] + fixture.stagepos[1] * window_size[1]

                color = self._get_fixture_color(fixture)
                color_u32 = imgui.get_color_u32(color)

                draw_list.add_circle_filled(
                    (center_x, center_y), fixture_radius, color_u32
                )

                if fixture in self.app.selected_fixtures:
                    draw_list.add_circle(
                        (center_x, center_y),
                        fixture_radius + 2,
                        imgui.get_color_u32((1, 1, 0, 1)),
                        thickness=2,
                    )

                text = str(fixture.start_address)
                text_size = imgui.calc_text_size(text)
                text_pos_x = center_x - text_size[0] / 2
                text_pos_y = center_y - text_size[1] / 2
                luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                text_color = (
                    imgui.get_color_u32((1, 1, 1, 1))
                    if luminance < 0.5
                    else imgui.get_color_u32((0, 0, 0, 1))
                )
                draw_list.add_text((text_pos_x, text_pos_y), text_color, text)

                imgui.set_cursor_screen_pos(
                    (center_x - fixture_radius, center_y - fixture_radius)
                )
                imgui.invisible_button(
                    f"stage_fixture_{fixture.start_address}_{id(fixture)}",
                    (fixture_radius * 2, fixture_radius * 2),
                )

                if imgui.is_item_active() and io.key_ctrl:
                    if fixture not in self.dragged_fixture_start_pos:
                        self.dragged_fixture_start_pos[fixture] = fixture.stagepos

                    if imgui.is_mouse_dragging(imgui.MouseButton.LEFT):
                        drag_delta = imgui.get_mouse_drag_delta(imgui.MouseButton.LEFT)
                        start_pos = self.dragged_fixture_start_pos[fixture]

                        new_x_rel = start_pos[0] + drag_delta[0] / window_size[0]
                        new_y_rel = start_pos[1] + drag_delta[1] / window_size[1]

                        fixture.stagepos = (
                            max(0.0, min(new_x_rel, 1.0)),
                            max(0.0, min(new_y_rel, 1.0)),
                        )

                elif imgui.is_item_clicked():
                    is_selected = fixture in self.app.selected_fixtures
                    if io.key_shift:
                        if is_selected:
                            self.app.selected_fixtures.remove(fixture)
                        else:
                            self.app.selected_fixtures.append(fixture)
                    else:
                        self.app.selected_fixtures.clear()
                        if not is_selected:
                            self.app.selected_fixtures.append(fixture)

                if (
                    not imgui.is_mouse_down(imgui.MouseButton.LEFT)
                    and fixture in self.dragged_fixture_start_pos
                ):
                    del self.dragged_fixture_start_pos[fixture]

                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.text(fixture.name)
                    imgui.separator()
                    intensity_percent = (
                        (fixture.intensity / 255.0)
                        if "intensity" in fixture.profile.channel_map
                        else 1.0
                    )  # type: ignore
                    imgui.text(f"Intensity: {intensity_percent:.0%}")
                    imgui.end_tooltip()

    def _get_fixture_color(
        self, fixture: ActiveFixture
    ) -> Tuple[float, float, float, float]:
        r, g, b = 0.0, 0.0, 0.0
        has_color = False
        if "red" in fixture.profile.channel_map:
            r = fixture.red / 255.0
            has_color = True  # type: ignore
        if "green" in fixture.profile.channel_map:
            g = fixture.green / 255.0
            has_color = True  # type: ignore
        if "blue" in fixture.profile.channel_map:
            b = fixture.blue / 255.0
            has_color = True  # type: ignore
        intensity = 1.0
        if "intensity" in fixture.profile.channel_map:
            intensity = fixture.intensity / 255.0  # type: ignore
        if has_color:
            return (r * intensity, g * intensity, b * intensity, 1.0)
        else:
            return (intensity, intensity, intensity, 1.0)


class App:
    def __init__(self, window: Any, renderer: GlfwRenderer):
        self.window = window
        self.renderer = renderer
        self.universes_window = UniversesWindow(self)
        self.patch_window = PatchWindow(self)
        self.gridview_window = GridviewWindow(self)
        self.stageview_window = StageviewWindow(self)
        self.windows: List[Window] = [
            self.universes_window,
            self.patch_window,
            self.gridview_window,
            self.stageview_window,
            ImguiAboutWindow(),
        ]
        self.universes: List[DMXUniverse] = []

        self.selected_fixtures: List[ActiveFixture] = []

    def update_universes(self):
        for universe in self.universes:
            universe.update()

    def draw(self):
        self.update_universes()
        self.draw_main_menu_bar()

        for window in self.windows:
            if window.is_open:
                window.draw()

    def add_window(self, window: Window) -> int:
        if window not in self.windows:
            self.windows.append(window)
            return len(self.windows) - 1
        raise ValueError("Already added this window!")

    def draw_main_menu_bar(self):
        """Draws the main menu bar at the top of the screen."""
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("View"):
                for window in self.windows:
                    changed, _ = imgui.menu_item(window.title, selected=window.is_open)

                    if changed:
                        window.is_open = not window.is_open

                imgui.end_menu()
            imgui.end_main_menu_bar()

    def remove_window(self, window: int | Window) -> Window | None:
        if isinstance(window, int):
            return self.windows.pop(window)
        else:
            self.windows.remove(window)
            return window
