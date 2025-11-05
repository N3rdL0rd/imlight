from dataclasses import dataclass, field
from enum import Enum
from slimgui.integrations.glfw import GlfwRenderer
from typing import Callable, List, Any, Optional, Tuple
from slimgui import imgui

from .fixture import ActiveFixture, ChannelType, DMXUniverse, DRIVERS, Layer, ShowLayer
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
        self.initial_x, self.initial_y = 0.08, 0.08
        self.spacing = 0.03

    def next_position(self) -> Tuple[float, float]:
        self.initial_x += self.spacing
        if self.initial_x > 1 - self.spacing:
            self.initial_y += self.spacing
            self.initial_x = 0.08
        return self.initial_x, self.initial_y

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
                        flags=imgui.SelectableFlags.ALLOW_OVERLAP | imgui.SelectableFlags.SPAN_ALL_COLUMNS
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
                    app=self.app,
                    profile=fixture_profile,
                    start_address=current_address,
                    start_stagepos=self.next_position(),
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
            r = fixture.red / 255.0  # type: ignore
            has_color = True
        if "green" in fixture.profile.channel_map:
            g = fixture.green / 255.0  # type: ignore
            has_color = True
        if "blue" in fixture.profile.channel_map:
            b = fixture.blue / 255.0  # type: ignore
            has_color = True
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
            if fixture.name != fixture.profile.model:
                imgui.text(f"{fixture.profile.manufacturer} - {fixture.profile.model}")
            imgui.separator()
            intensity_percent = (
                (fixture.intensity / 255.0)  # type: ignore
                if "intensity" in fixture.profile.channel_map
                else 1.0
            )
            imgui.text(f"Intensity: {intensity_percent:.0%}")
            imgui.end_tooltip()


class StageviewWindow(TexturedWindow):
    SNAP_THRESHOLD = 0.03

    def __init__(self, app: "App"):
        super().__init__(
            title="Stageview", aspect_ratio=2500 / 2658, image_path="stage.png"
        )
        self.app = app
        self.is_open = True
        self.is_dragging_selection = False
        self.dragged_fixtures_start_pos: dict[ActiveFixture, Tuple[float, float]] = {}
        self.is_marquee_selecting = False
        self.marquee_start_pos = (0, 0)
        self.fixtures_in_marquee_rect = set()

    def pre_draw(self):
        super().pre_draw()
        imgui.set_next_window_pos((1370, 30), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((730, 780), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        draw_list = imgui.get_window_draw_list()
        window_pos = imgui.get_window_pos()
        window_size = imgui.get_window_size()
        io = imgui.get_io()

        num_electrics = self.app.num_electrics
        if num_electrics > 0:
            line_color = imgui.get_color_u32((0.1, 0.1, 0.1, 1.0))
            top_third_height = window_size[1] / 3.0
            for i in range(1, num_electrics + 1):
                y_pos = window_pos[1] + (i / (num_electrics + 1)) * top_third_height
                draw_list.add_line(
                    (window_pos[0] + window_size[0] / 20, y_pos),
                    (window_pos[0] + window_size[0] - window_size[0] / 20, y_pos),
                    line_color,
                    thickness=2,
                )

        if (
            imgui.is_window_hovered()
            and io.key_ctrl
            and io.key_shift
            and imgui.is_mouse_clicked(imgui.MouseButton.LEFT)
        ):
            self.is_marquee_selecting = True
            self.marquee_start_pos = io.mouse_pos
            self.fixtures_in_marquee_rect.clear()

        if self.is_marquee_selecting and imgui.is_mouse_released(
            imgui.MouseButton.LEFT
        ):
            current_selection_set = set(self.app.selected_fixtures)
            final_selection_set = current_selection_set.union(
                self.fixtures_in_marquee_rect
            )
            self.app.selected_fixtures = list(final_selection_set)
            self.is_marquee_selecting = False
            self.fixtures_in_marquee_rect.clear()

        if self.is_marquee_selecting:
            self.fixtures_in_marquee_rect.clear()

        if self.is_dragging_selection:
            drag_delta = imgui.get_mouse_drag_delta(imgui.MouseButton.LEFT)
            for fixture, start_pos in self.dragged_fixtures_start_pos.items():
                new_x_rel = start_pos[0] + drag_delta[0] / window_size[0]
                new_y_rel = start_pos[1] + drag_delta[1] / window_size[1]
                fixture.stagepos = (
                    max(0.0, min(new_x_rel, 1.0)),
                    max(0.0, min(new_y_rel, 1.0)),
                )

        if (
            not imgui.is_mouse_down(imgui.MouseButton.LEFT)
            and self.is_dragging_selection
        ):
            if num_electrics > 0:
                top_third_relative = 1.0 / 3.0
                grid_y_positions = [
                    (i / (num_electrics + 1)) * top_third_relative
                    for i in range(1, num_electrics + 1)
                ]
                for fixture in self.dragged_fixtures_start_pos.keys():
                    current_y = fixture.stagepos[1]
                    closest_y = min(grid_y_positions, key=lambda y: abs(y - current_y))
                    if abs(current_y - closest_y) <= self.SNAP_THRESHOLD:
                        fixture.stagepos = (fixture.stagepos[0], closest_y)

            self.is_dragging_selection = False
            self.dragged_fixtures_start_pos.clear()

        fixture_radius = 10
        for universe in self.app.universes:
            for fixture in universe.fixtures:
                center_x = window_pos[0] + fixture.stagepos[0] * window_size[0]
                center_y = window_pos[1] + fixture.stagepos[1] * window_size[1]

                color = self._get_fixture_color(fixture)
                draw_list.add_circle_filled(
                    (center_x, center_y), fixture_radius, imgui.get_color_u32(color)
                )

                is_currently_selected = (
                    fixture in self.app.selected_fixtures
                    or fixture in self.fixtures_in_marquee_rect
                )
                if is_currently_selected:
                    draw_list.add_circle(
                        (center_x, center_y),
                        fixture_radius + 2,
                        imgui.get_color_u32((1, 1, 0, 1)),
                        thickness=2,
                    )

                text = str(fixture.start_address)
                text_size = imgui.calc_text_size(text)
                luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                text_color = (
                    imgui.get_color_u32((1, 1, 1, 1))
                    if luminance < 0.5
                    else imgui.get_color_u32((0, 0, 0, 1))
                )
                draw_list.add_text(
                    (center_x - text_size[0] / 2, center_y - text_size[1] / 2),
                    text_color,
                    text,
                )

                imgui.set_cursor_screen_pos(
                    (center_x - fixture_radius, center_y - fixture_radius)
                )
                imgui.invisible_button(
                    f"stage_fixture_{fixture.start_address}_{id(fixture)}",
                    (fixture_radius * 2, fixture_radius * 2),
                )

                if self.is_marquee_selecting:
                    marquee_min = (
                        min(self.marquee_start_pos[0], io.mouse_pos[0]),
                        min(self.marquee_start_pos[1], io.mouse_pos[1]),
                    )
                    marquee_max = (
                        max(self.marquee_start_pos[0], io.mouse_pos[0]),
                        max(self.marquee_start_pos[1], io.mouse_pos[1]),
                    )
                    if (
                        marquee_min[0] <= center_x <= marquee_max[0]
                        and marquee_min[1] <= center_y <= marquee_max[1]
                    ):
                        self.fixtures_in_marquee_rect.add(fixture)

                if imgui.is_item_active() and io.key_ctrl and not io.key_shift:
                    if not self.is_dragging_selection:
                        self.is_dragging_selection = True
                        imgui.reset_mouse_drag_delta(imgui.MouseButton.LEFT)
                        if fixture not in self.app.selected_fixtures:
                            self.app.selected_fixtures = [fixture]

                        self.dragged_fixtures_start_pos.clear()
                        for f in self.app.selected_fixtures:
                            self.dragged_fixtures_start_pos[f] = f.stagepos

                elif imgui.is_item_clicked() and not self.is_marquee_selecting:
                    is_selected = fixture in self.app.selected_fixtures
                    if io.key_shift:
                        if is_selected:
                            self.app.selected_fixtures.remove(fixture)
                        else:
                            self.app.selected_fixtures.append(fixture)
                    elif not io.key_ctrl:
                        self.app.selected_fixtures.clear()
                        if not is_selected:
                            self.app.selected_fixtures.append(fixture)

                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.text(fixture.name)
                    imgui.separator()
                    intensity_percent = (
                        (fixture.intensity / 255.0)  # type: ignore
                        if "intensity" in fixture.profile.channel_map
                        else 1.0
                    )
                    imgui.text(f"Intensity: {intensity_percent:.0%}")
                    imgui.end_tooltip()

        if self.is_marquee_selecting:
            rect_color = imgui.get_color_u32((0.2, 0.4, 1.0, 0.25))
            border_color = imgui.get_color_u32((0.4, 0.6, 1.0, 0.8))
            draw_list.add_rect_filled(self.marquee_start_pos, io.mouse_pos, rect_color)
            draw_list.add_rect(
                self.marquee_start_pos, io.mouse_pos, border_color, thickness=1.0
            )

    def _get_fixture_color(
        self, fixture: ActiveFixture
    ) -> Tuple[float, float, float, float]:
        r, g, b = 0.0, 0.0, 0.0
        has_color = False
        if "red" in fixture.profile.channel_map:
            r = fixture.red / 255.0  # type: ignore
            has_color = True
        if "green" in fixture.profile.channel_map:
            g = fixture.green / 255.0  # type: ignore
            has_color = True
        if "blue" in fixture.profile.channel_map:
            b = fixture.blue / 255.0  # type: ignore
            has_color = True
        intensity = 1.0
        if "intensity" in fixture.profile.channel_map:
            intensity = fixture.intensity / 255.0  # type: ignore
        if has_color:
            return (r * intensity, g * intensity, b * intensity, 1.0)
        else:
            return (intensity, intensity, intensity, 1.0)


@dataclass
class Argument:
    """Defines a single argument for a command."""

    name: str
    description: str
    type_hint: str


@dataclass
class Command:
    """Defines a command, its metadata, and its handler function."""

    name: str
    description: str
    handler: Callable
    aliases: List[str] = field(default_factory=list)
    arguments: List[Argument] = field(default_factory=list)


class CommanderWindow(Window):
    """
    An input window for executing custom, defined commands with rich
    autocompletion and signature help.
    """

    def __init__(self, app: "App"):
        super().__init__("Commander")
        self.app = app
        self.is_open = True

        self.input_buffer = ""
        self.history: List[Tuple[str, str]] = []
        self.command_history: List[str] = []
        self.command_history_pos: int = -1

        self.suggestions = []
        self.active_suggestion: int = -1
        self.show_autocomplete = False

        self.commands, self.unique_commands = self._define_commands()

    def pre_draw(self):
        imgui.set_next_window_pos((580, 520), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((780, 290), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        for command, output in self.history:
            imgui.text_colored((0.6, 0.8, 1.0, 1.0), f"> {command}")
            if output:
                is_error = "Error" in output or "Unknown command" in output
                color = (1.0, 0.8, 0.8, 1.0) if is_error else (1.0, 1.0, 1.0, 1.0)
                imgui.push_style_color(imgui.Col.TEXT, color)
                imgui.text_wrapped(output)
                imgui.pop_style_color()
        imgui.set_scroll_y(imgui.get_scroll_max_y())

        self._handle_input_keyboard()

        changed, self.input_buffer = imgui.input_text(
            "##Input", self.input_buffer, flags=imgui.InputTextFlags.ENTER_RETURNS_TRUE
        )

        if changed:
            self._execute_command(self.input_buffer)
            self.input_buffer = ""
            imgui.set_keyboard_focus_here(-1)
            self.command_history_pos = -1
            self.show_autocomplete = False

        if imgui.is_item_focused() and self.input_buffer:
            self._update_autocomplete()
            self._draw_autocomplete_popup()
            self._draw_signature_help_popup()
        else:
            self.show_autocomplete = False

    def _handle_input_keyboard(self):
        if not imgui.is_item_focused():
            return

        is_up = imgui.is_key_pressed(imgui.Key.KEY_UP_ARROW)
        is_down = imgui.is_key_pressed(imgui.Key.KEY_DOWN_ARROW)
        is_tab = imgui.is_key_pressed(imgui.Key.KEY_TAB)

        if is_up and self.command_history:
            if self.command_history_pos < len(self.command_history) - 1:
                self.command_history_pos += 1
                self.input_buffer = self.command_history[
                    -(self.command_history_pos + 1)
                ]

        if is_down and self.command_history:
            if self.command_history_pos > 0:
                self.command_history_pos -= 1
                self.input_buffer = self.command_history[
                    -(self.command_history_pos + 1)
                ]
            else:
                self.command_history_pos = -1
                self.input_buffer = ""

        if is_tab and self.suggestions:
            self.active_suggestion = (self.active_suggestion + 1) % len(
                self.suggestions
            )
            self.input_buffer = self.suggestions[self.active_suggestion]

    def _execute_command(self, command_str: str):
        if not command_str:
            return
        self.command_history.append(command_str)

        parts = command_str.split()
        cmd_name = parts[0]
        args = parts[1:]

        command = self.commands.get(cmd_name)
        if command:
            try:
                output = command.handler(*args)
            except Exception as e:
                output = f"Error executing command: {e}"
        else:
            output = f"Error: Unknown command '{cmd_name}'. Type 'help' for a list of commands."

        self.history.append((command_str, str(output).strip()))

    def _update_autocomplete(self):
        cmd_name = self.input_buffer.split()[0]
        suggestions = sorted([cmd for cmd in self.commands if cmd.startswith(cmd_name)])
        if suggestions:
            self.suggestions = suggestions
            self.show_autocomplete = True
            self.active_suggestion = -1
        else:
            self.show_autocomplete = False

    def _draw_autocomplete_popup(self):
        if not self.show_autocomplete:
            return

        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        popup_pos = (rect_min[0], rect_max[1] + 4)

        imgui.set_next_window_pos(popup_pos)
        imgui.begin(
            "Autocomplete",
            flags=imgui.WindowFlags.NO_TITLE_BAR
            | imgui.WindowFlags.NO_MOVE
            | imgui.WindowFlags.NO_RESIZE
            | imgui.WindowFlags.CHILD_WINDOW
            | imgui.WindowFlags.NO_SAVED_SETTINGS,
        )

        for i, suggestion in enumerate(self.suggestions):
            if imgui.selectable(suggestion, self.active_suggestion == i)[0]:
                self.input_buffer = suggestion + " "
                self.show_autocomplete = False
        imgui.end_child()

    def _draw_signature_help_popup(self):
        parts = self.input_buffer.split()
        if not parts:
            return
        cmd_name = parts[0]
        command = self.commands.get(cmd_name)
        if not command or not command.arguments:
            return

        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        base_y = rect_max[1] + 4
        if self.show_autocomplete:
            base_y += len(self.suggestions) * 10

        imgui.set_next_window_pos((rect_min[0], base_y))
        imgui.begin(
            "SignatureHelp",
            flags=imgui.WindowFlags.NO_TITLE_BAR
            | imgui.WindowFlags.NO_MOVE
            | imgui.WindowFlags.NO_RESIZE
            | imgui.WindowFlags.CHILD_WINDOW
            | imgui.WindowFlags.NO_SAVED_SETTINGS
            | imgui.WindowFlags.ALWAYS_AUTO_RESIZE,
        )

        imgui.text(command.description)
        imgui.separator()

        current_arg_index = len(parts) - 1

        for i, arg in enumerate(command.arguments):
            is_current = i == current_arg_index
            if is_current:
                imgui.push_style_color(imgui.Col.TEXT, (1, 1, 0, 1))
            imgui.text(f"{arg.name} ({arg.type_hint}):")
            imgui.same_line()
            imgui.text(arg.description)
            if is_current:
                imgui.pop_style_color()

        imgui.end_child()

    def _define_commands(self) -> Tuple[dict, List[Command]]:
        """Central place to define commands, returning the full map and a unique list."""
        cmds = [
            Command(
                name="help",
                description="Shows a list of all available commands.",
                handler=self._command_help,
                aliases=["h"],
            ),
            Command(
                name="select",
                description="Selects fixtures by address or name, clearing previous selection.",
                handler=self._command_select,
                aliases=["s"],
                arguments=[
                    Argument(
                        "target",
                        "An address like '@12' or a partial name like 'spot'.",
                        "@<addr>|<name>",
                    )
                ],
            ),
            Command(
                name="add",
                description="Adds fixtures to the current selection.",
                handler=self._command_add,
                aliases=["a"],
                arguments=[
                    Argument(
                        "target",
                        "An address like '@12' or a partial name like 'spot'.",
                        "@<addr>|<name>",
                    )
                ],
            ),
            Command(
                name="clear",
                description="Clears the current fixture selection.",
                handler=self._command_clear,
                aliases=["c"],
            ),
            Command(
                name="layer",
                description="Sets a channel value on a layer for all selected fixtures.",
                handler=self._command_layer,
                aliases=["l"],
                arguments=[
                    Argument(
                        "layer_name",
                        "The name of the layer to modify (e.g., 'main').",
                        "<name>",
                    ),
                    Argument(
                        "channel",
                        "The channel to change (e.g., 'red', 'intensity').",
                        "<channel>",
                    ),
                    Argument("value", "The DMX value to set.", "0-255"),
                ],
            ),
            Command(
                name="electrics",
                description="Sets the number of stage electrics in this show.",
                handler=self._command_electrics,
                aliases=[],
                arguments=[Argument("num", "The number of electrics", "0-8")],
            ),
            Command(
                name="name",
                description="Sets the name of the selected fixture, or if multiple are selected, sets their names with sequential appended numbers.",
                handler=self._command_name,
                aliases=["n"],
                arguments=[
                    Argument(
                        "name",
                        "The name to set for a single fixture, or the base name to set for multiple",
                        "<name>",
                    )
                ],
            ),
        ]

        command_map = {}
        for cmd in cmds:
            command_map[cmd.name] = cmd
            for alias in cmd.aliases:
                command_map[alias] = cmd
        return command_map, cmds

    def _command_name(self, *args: str):
        if not args:
            return "Error: Missing argument. Usage: name <name>"
        if not (len(self.app.selected_fixtures) >= 1):
            return "Error: Please select at least one fixture to set the name of."
        name = args[0]
        if len(self.app.selected_fixtures) == 1:
            self.app.selected_fixtures[0].name = name
        else:
            for i, fixture in enumerate(self.app.selected_fixtures):
                fixture.name = f"{name} {i + 1}"
        return f"Renamed {len(self.app.selected_fixtures)} fixture{'s' if len(self.app.selected_fixtures) > 1 else ''}."

    def _command_electrics(self, *args: str):
        if not args:
            return "Error: Missing argument. Usage: select <num>"
        num = int(args[0])
        if num > 8 or num < 0:
            return "Error: Please choose a number of electrics between 0 and 8."
        self.app.num_electrics = num
        return f"Set electric count to {num}."

    def _command_help(self, *args):
        lines = ["Available Commands:"]
        for cmd in self.unique_commands:
            name_str = cmd.name
            if cmd.aliases:
                name_str += f" ({', '.join(cmd.aliases)})"
            arg_str = " ".join(f"<{arg.name}>" for arg in cmd.arguments)
            lines.append(f"  {name_str} {arg_str}")
        return "\n".join(lines)

    def _find_fixtures(self, target: str) -> List["ActiveFixture"]:
        found = []
        if target == "*":
            res = []
            for u in self.app.universes:
                for f in u.fixtures:
                    res.append(f)
            return res
        if target.startswith("@"):
            try:
                address = int(target[1:])
                for u in self.app.universes:
                    for f in u.fixtures:
                        if f.start_address == address:
                            found.append(f)
                            break
            except ValueError:
                pass
        else:
            for u in self.app.universes:
                for f in u.fixtures:
                    if target.lower() in f.name.lower():
                        found.append(f)
        return found

    def _command_select(self, *args):
        if not args:
            return "Error: Missing argument. Usage: select <target>"
        target = args[0]
        fixtures_to_select = self._find_fixtures(target)
        if not fixtures_to_select:
            return f"No fixtures found matching '{target}'."
        self.app.selected_fixtures = fixtures_to_select
        return f"Selected {len(fixtures_to_select)} fixture(s)."

    def _command_add(self, *args):
        if not args:
            return "Error: Missing argument. Usage: add <target>"
        target = args[0]
        fixtures_to_add = self._find_fixtures(target)
        if not fixtures_to_add:
            return f"No fixtures found matching '{target}'."

        current_selection = set(self.app.selected_fixtures)
        for f in fixtures_to_add:
            current_selection.add(f)
        self.app.selected_fixtures = list(current_selection)
        return f"Selection now contains {len(self.app.selected_fixtures)} fixture(s)."

    def _command_clear(self, *args):
        self.app.selected_fixtures.clear()
        return "Selection cleared."

    def _command_layer(self, *args):
        if len(args) < 3:
            return "Error: Not enough arguments. Usage: layer <layer_name> <channel> <value>"

        layer_name, channel, value_str = args[0], args[1], args[2]

        if not self.app.selected_fixtures:
            return "Error: No fixtures selected."

        try:
            value = int(value_str)
            if not (0 <= value <= 255):
                raise ValueError("Value out of 0-255 range.")
        except ValueError:
            return f"Error: Invalid value '{value_str}'. Must be an integer between 0 and 255."

        affected_count = 0
        unsupported_count = 0
        for fixture in self.app.selected_fixtures:
            # Accessing the layer via dictionary syntax creates it if it doesn't exist
            layer = fixture.layers[layer_name]

            # Check if the fixture's profile actually supports this channel
            if channel in fixture.profile.channel_map:
                setattr(layer, channel, value)
                affected_count += 1
            else:
                unsupported_count += 1

        msg = f"Set '{channel}' to {value} on layer '{layer_name}' for {affected_count} fixture(s)."
        if unsupported_count > 0:
            msg += f" ({unsupported_count} selected fixture(s) do not support this channel)."
        return msg

        
class FaderDisplayMode(Enum):
    FOLLOW_SELECTION = "Follow Selection"
    ALL_PATCHED = "All Patched"
    FILTER = "Filter (NYI)"
    
class LayersWindow(Window):
    """A window for managing global show layers and their priorities."""
    def __init__(self, app: "App"):
        super().__init__("Layers")
        self.app = app
        self.new_layer_name = ""
        self.status_message = ""
        self.status_is_error = False

    def pre_draw(self):
        imgui.set_next_window_size((400, 300), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((1370, 820), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        imgui.text("Add New Global Layer")
        changed, self.new_layer_name = imgui.input_text("##newlayer", self.new_layer_name, 64)
        imgui.same_line()
        if imgui.button("Add Layer"):
            if not self.new_layer_name:
                self.status_message = "Error: Layer name cannot be empty."
                self.status_is_error = True
            elif self.app.get_show_layer(self.new_layer_name):
                self.status_message = "Error: A layer with this name already exists."
                self.status_is_error = True
            else:
                self.app.add_show_layer(self.new_layer_name)
                self.status_message = f"Successfully added layer '{self.new_layer_name}'."
                self.status_is_error = False
                self.new_layer_name = ""

        if self.status_message:
            color = (1, 0, 0, 1) if self.status_is_error else (0, 1, 0, 1)
            imgui.text_colored(color, self.status_message)
        
        imgui.separator()
        imgui.text("Layer Priorities")

        if imgui.begin_table("layers_table", 3, flags=imgui.TableFlags.BORDERS):
            imgui.table_setup_column("Name", flags=imgui.TableColumnFlags.WIDTH_STRETCH)
            imgui.table_setup_column("Priority", flags=imgui.TableColumnFlags.WIDTH_STRETCH)
            imgui.table_setup_column("Actions", flags=imgui.TableColumnFlags.WIDTH_FIXED, init_width_or_weight=60)
            imgui.table_headers_row()

            layer_to_remove = None
            for i, show_layer in enumerate(self.app.layers):
                imgui.table_next_row()
                
                imgui.table_next_column()
                imgui.text(show_layer.name)

                imgui.table_next_column()
                imgui.push_item_width(-1)
                changed, new_priority = imgui.slider_float(f"##priority_{i}", show_layer.priority, 0.0, 1.0, "%.2f")
                if changed:
                    show_layer.priority = new_priority
                    for u in self.app.universes:
                        for f in u.fixtures:
                            f.compose()
                imgui.pop_item_width()

                imgui.table_next_column()
                if len(self.app.layers) > 1:
                    if imgui.button(f"Remove##{i}"):
                        layer_to_remove = show_layer.name

            imgui.end_table()
            
            if layer_to_remove:
                self.app.remove_show_layer(layer_to_remove)
                self.status_message = f"Removed layer '{layer_to_remove}'."
                self.status_is_error = False


class FaderWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Faders")
        self.app = app
        self.is_open = True
        self.target_layer = "manual"
        self.target_channel_type = ChannelType.INTENSITY
        self.display_mode = FaderDisplayMode.FOLLOW_SELECTION
        self.window_flags |= imgui.WindowFlags.MENU_BAR

    def pre_draw(self):
        imgui.set_next_window_size((780, 340), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((580, 820), imgui.Cond.FIRST_USE_EVER)

    def _draw_menu_bar(self):
        if imgui.begin_menu_bar():
            if imgui.begin_menu(f"Layer: {self.target_layer}"):
                for show_layer in self.app.layers:
                    changed, _ = imgui.menu_item(show_layer.name, selected=(self.target_layer == show_layer.name))
                    if changed:
                        self.target_layer = show_layer.name
                imgui.end_menu()

            if imgui.begin_menu("Mode"):
                for mode in FaderDisplayMode:
                    changed, _ = imgui.menu_item(
                        mode.value, selected=(self.display_mode == mode)
                    )
                    if changed:
                        self.display_mode = mode
                imgui.end_menu()

            imgui.end_menu_bar()

    def _get_channel_name_for_type(
        self, fixture: ActiveFixture, channel_type: ChannelType
    ) -> str | None:
        for ch_def in fixture.profile.channels:
            if ch_def.channel_type == channel_type:
                return ch_def.name
        return None

    def draw_content(self):
        self._draw_menu_bar()

        fixtures_to_show = []
        if self.display_mode == FaderDisplayMode.FOLLOW_SELECTION:
            fixtures_to_show = self.app.selected_fixtures
        elif self.display_mode == FaderDisplayMode.ALL_PATCHED:
            for u in self.app.universes:
                fixtures_to_show.extend(u.fixtures)
        fixtures_to_show.sort(key=lambda f: f.start_address)

        if not fixtures_to_show:
            imgui.text("No fixtures to display.")
            return

        relevant_fixtures = []
        for f in fixtures_to_show:
            channel_name = self._get_channel_name_for_type(f, self.app.channel_type)
            if channel_name is not None:
                relevant_fixtures.append((f, channel_name))

        if not relevant_fixtures:
            pretty_name = self.app.channel_type.name.replace("_", " ").title()
            imgui.text(
                f"No fixtures in the current view support the '{pretty_name}' channel."
            )
            return

        fader_total_width = 60
        available_width = imgui.get_content_region_avail()[0]
        num_columns = max(1, int(available_width / fader_total_width))
        imgui.columns(num_columns, "fader_grid", border=False)

        slider_height = imgui.get_content_region_avail()[1] - 50

        for fixture, channel_name in relevant_fixtures:
            imgui.push_id(f"fader_{fixture.start_address}_{channel_name}")
            layer = fixture.layers[self.target_layer]
            ch_def = fixture.profile.channel_map[channel_name]
            current_value = int(layer.dmx_values[ch_def.relative_offset])
            changed, new_value = imgui.vslider_int(
                "##vslider",
                (40, slider_height),
                current_value,
                0,
                255,
            )
            if changed:
                setattr(layer, channel_name, new_value)
            imgui.text(f"@{fixture.start_address}")
            imgui.push_font(None, font_size_base=11)
            imgui.text_wrapped(fixture.name)
            imgui.pop_font()
            imgui.next_column()
            imgui.pop_id()
        imgui.columns(1)


class App:
    def __init__(self, window: Any, renderer: GlfwRenderer):
        self.window = window
        self.renderer = renderer
        self.layers: List[ShowLayer] = [
            ShowLayer("manual", 1.0),
            ShowLayer("effects", 1.0),
            ShowLayer("cues", 1.0),
        ]
        self.universes_window = UniversesWindow(self)
        self.patch_window = PatchWindow(self)
        self.gridview_window = GridviewWindow(self)
        self.stageview_window = StageviewWindow(self)
        self.commander_window = CommanderWindow(self)
        self.fader_window = FaderWindow(self)
        self.layers_window = LayersWindow(self) 
        self.windows: List[Window] = [
            self.universes_window,
            self.patch_window,
            self.gridview_window,
            self.stageview_window,
            self.commander_window,
            self.fader_window,
            self.layers_window,
            ImguiAboutWindow(),
        ]
        self.universes: List[DMXUniverse] = []
        self.selected_fixtures: List[ActiveFixture] = []
        self.num_electrics: int = 4
        self.channel_type: ChannelType = ChannelType.INTENSITY

    def get_show_layer(self, name: str) -> Optional[ShowLayer]:
        """Finds a global ShowLayer by its name."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def add_show_layer(self, name: str, priority: float = 1.0):
        """Adds a new global layer to the show and all existing fixtures."""
        if self.get_show_layer(name):
            return
        
        self.layers.append(ShowLayer(name, priority))
        for universe in self.universes:
            for fixture in universe.fixtures:
                if name not in fixture.layers:
                    fixture.layers._layers[name] = Layer(name, fixture.profile, fixture)
    
    def remove_show_layer(self, name: str):
        """Removes a global layer from the show and all existing fixtures."""
        layer_to_remove = self.get_show_layer(name)
        if layer_to_remove:
            self.layers.remove(layer_to_remove)
            for universe in self.universes:
                for fixture in universe.fixtures:
                    if name in fixture.layers:
                        del fixture.layers[name]

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
            if imgui.begin_menu("Stageview"):
                imgui.text("Electrics")
                imgui.separator()
                for i in range(1, 9):
                    changed, _ = imgui.menu_item(
                        f"{i}", selected=(self.num_electrics == i)
                    )
                    if changed:
                        self.num_electrics = i
                imgui.separator()
                changed, _ = imgui.menu_item("None", selected=(self.num_electrics == 0))
                if changed:
                    self.num_electrics = 0

                imgui.end_menu()
            if imgui.begin_menu(f"Channel: {self.channel_type.name.replace("_", " ").title()}"):
                for channel_type in ChannelType:
                    pretty_name = channel_type.name.replace("_", " ").title()
                    changed, _ = imgui.menu_item(
                        pretty_name, selected=(self.channel_type == channel_type)
                    )
                    if changed:
                        self.channel_type = channel_type
                imgui.end_menu()
            imgui.end_main_menu_bar()

    def remove_window(self, window: int | Window) -> Window | None:
        if isinstance(window, int):
            return self.windows.pop(window)
        else:
            self.windows.remove(window)
            return window
