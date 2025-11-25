from typing import Any, Callable, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
import moderngl

from .viz import VizWindow
from .fixture import (
    ActiveFixture,
    ChannelType,
    ConfigParameterType,
    DMXUniverse,
    DRIVERS,
    DriverInitError,
    Layer,
    ShowLayer,
)
from .fixture.all import ALL_FIXTURES
from .window import Window, ImguiAboutWindow, TexturedWindow

# --- Windows Classes ---

class UniversesWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Universes")
        self.app = app
        self.drivers = [driver.clean_name for driver in DRIVERS]
        self.drivers.append("None")
        self.configuring_driver_index: Optional[int] = None
        self.temp_config: dict = {}
        self.driver_init_error: Optional[str] = None

    def draw_content(self):
        if imgui.button("Add New Universe"):
            self.app.universes.append(DMXUniverse())
        imgui.separator()

        if self.driver_init_error:
            imgui.text_colored(imgui.ImVec4(1, 0, 0, 1), self.driver_init_error)

        if imgui.begin_table("universes", 4, flags=imgui.TableFlags_.borders):
            imgui.table_setup_column("ID", flags=imgui.TableColumnFlags_.width_fixed, init_width_or_weight=30)
            imgui.table_setup_column("Driver", flags=imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("Fixtures", flags=imgui.TableColumnFlags_.width_fixed, init_width_or_weight=60)
            imgui.table_setup_column("Actions", flags=imgui.TableColumnFlags_.width_fixed, init_width_or_weight=150)
            imgui.table_headers_row()

            universe_to_remove_index = None
            for i, universe in enumerate(self.app.universes):
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(str(i))

                imgui.table_next_column()
                current_driver_name = "None" if universe.driver is None else universe.driver.__class__.clean_name
                try:
                    selected_idx = self.drivers.index(current_driver_name)
                except ValueError:
                    selected_idx = len(self.drivers) - 1
                
                imgui.push_item_width(-1)
                changed, new_idx = imgui.combo(f"##driver_combo_{i}", selected_idx, self.drivers)
                imgui.pop_item_width()

                if changed:
                    if self.drivers[new_idx] == "None":
                        universe.driver = None
                    else:
                        try:
                            driver_class = DRIVERS[new_idx]
                            new_driver = driver_class()
                            new_driver.on_config_changed()
                            universe.driver = new_driver
                            self.driver_init_error = None
                        except DriverInitError as e:
                            universe.driver = None
                            self.driver_init_error = str(e)

                imgui.table_next_column()
                imgui.text(str(len(universe.fixtures)))

                imgui.table_next_column()
                if universe.driver and universe.driver.CONFIG_PARAMS:
                    if imgui.button(f"Configure##{i}"):
                        self.configuring_driver_index = i
                        self.temp_config = universe.driver.config.copy()
                        imgui.open_popup("Driver Configuration")
                    imgui.same_line()

                if imgui.button(f"Remove##{i}"):
                    universe_to_remove_index = i

            imgui.end_table()

            if universe_to_remove_index is not None:
                removed_universe = self.app.universes.pop(universe_to_remove_index)
                # Cleanup selection
                self.app.selected_fixtures = [f for f in self.app.selected_fixtures if f not in removed_universe.fixtures]

        self._draw_config_popup()
        self._draw_driver_error_popup()

    def _draw_config_popup(self):
        if imgui.begin_popup_modal("Driver Configuration", True, flags=imgui.WindowFlags_.always_auto_resize)[0]:
            if self.configuring_driver_index is not None:
                try:
                    driver = self.app.universes[self.configuring_driver_index].driver
                    if driver:
                        imgui.text(f"Settings for {driver.clean_name} Driver")
                        imgui.separator()
                        for param in driver.CONFIG_PARAMS:
                            current_val = self.temp_config.get(param.name, param.default_value)
                            
                            if param.param_type == ConfigParameterType.INT:
                                changed, new_val = imgui.slider_int(
                                    param.name.title(), current_val, 
                                    param.constraints.get("min", 0), param.constraints.get("max", 255)
                                )
                                if changed: self.temp_config[param.name] = new_val
                            elif param.param_type == ConfigParameterType.STRING:
                                changed, new_val = imgui.input_text(param.name.title(), current_val)
                                if changed: self.temp_config[param.name] = new_val
                            elif param.param_type == ConfigParameterType.BOOL:
                                changed, new_val = imgui.checkbox(param.name.title(), current_val)
                                if changed: self.temp_config[param.name] = new_val
                                
                        imgui.separator()
                        if imgui.button("Save"):
                            driver.config = self.temp_config.copy()
                            driver.on_config_changed()
                            imgui.close_current_popup()
                        imgui.same_line()
                        if imgui.button("Cancel"):
                            imgui.close_current_popup()
                except Exception:
                    imgui.close_current_popup()
            imgui.end_popup()

    def _draw_driver_error_popup(self):
        if imgui.begin_popup_modal("Driver Error", True, flags=imgui.WindowFlags_.always_auto_resize)[0]:
            if self.driver_init_error:
                imgui.text("Could not initialize DMX driver.")
                imgui.text_wrapped(self.driver_init_error)
            if imgui.button("OK"):
                imgui.close_current_popup()
                self.driver_init_error = None
            imgui.end_popup()


class PatchWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Patch")
        self.app = app
        self.fixture_profiles = ALL_FIXTURES
        self.fixture_names = [f"{f.manufacturer} - {f.model}" for f in self.fixture_profiles]
        self.selected_universe_index = 0
        self.selected_fixture_index = 0
        self.start_address = 1
        self.fixture_count = 1
        self.status_message = ""
        self.status_is_error = False
        self.initial_x, self.initial_y = 0.08, 0.08

    def next_position(self) -> Tuple[float, float]:
        self.initial_x += 0.03
        if self.initial_x > 0.97:
            self.initial_y += 0.03
            self.initial_x = 0.08
        return self.initial_x, self.initial_y

    def draw_content(self):
        imgui.text("Add New Fixture(s)")
        imgui.separator()

        if not self.app.universes:
            imgui.text("Please add a universe first.")
            return

        universe_names = [f"Universe {i + 1}" for i in range(len(self.app.universes))]
        _, self.selected_universe_index = imgui.combo("Target Universe", self.selected_universe_index, universe_names)
        _, self.selected_fixture_index = imgui.combo("Fixture Type", self.selected_fixture_index, self.fixture_names)
        _, self.start_address = imgui.input_int("Start Address", self.start_address)
        _, self.fixture_count = imgui.input_int("Count", self.fixture_count)

        if imgui.button("Patch Fixtures"):
            self.patch_fixtures()

        if self.status_message:
            color = imgui.ImVec4(1, 0, 0, 1) if self.status_is_error else imgui.ImVec4(0, 1, 0, 1)
            imgui.text_colored(color, self.status_message)

        imgui.separator()
        imgui.text("Patched Fixtures")
        
        if imgui.begin_child("patched_fixtures_list"):
            if len(self.app.universes) > self.selected_universe_index:
                target_universe = self.app.universes[self.selected_universe_index]
                if imgui.begin_table("patched_list", 3, flags=imgui.TableFlags_.borders):
                    imgui.table_setup_column("Addr")
                    imgui.table_setup_column("Name")
                    imgui.table_setup_column("Actions")
                    imgui.table_headers_row()

                    to_remove = None
                    for fix in target_universe.fixtures:
                        imgui.table_next_row()
                        imgui.table_next_column()
                        imgui.text(str(fix.start_address))
                        imgui.table_next_column()
                        imgui.text(fix.profile.model)
                        imgui.table_next_column()
                        if imgui.button(f"Remove##{fix.start_address}"):
                            to_remove = fix
                    
                    if to_remove:
                        target_universe.fixtures.remove(to_remove)
                        if to_remove in self.app.selected_fixtures:
                            self.app.selected_fixtures.remove(to_remove)
                    imgui.end_table()
            imgui.end_child()

    def patch_fixtures(self):
        try:
            target_universe = self.app.universes[self.selected_universe_index]
            profile = self.fixture_profiles[self.selected_fixture_index]
            addr = self.start_address
            for _ in range(self.fixture_count):
                fix = ActiveFixture(self.app, profile, addr, self.next_position())
                target_universe.add_fixture(fix)
                addr += profile.channel_count
            self.status_message = f"Patched {self.fixture_count} fixtures."
            self.status_is_error = False
            self.start_address = addr
        except Exception as e:
            self.status_message = str(e)
            self.status_is_error = True


class GridviewWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Gridview")
        self.app = app
        self.is_drag_selecting = False
        self.drag_start_pos = imgui.ImVec2(0, 0)
        self.fixtures_in_drag = set()

    def draw_content(self):
        tile_size = 60
        avail_x = imgui.get_content_region_avail().x
        cols = max(1, int(avail_x / (tile_size + 4)))
        
        imgui.columns(cols, "grid", False)
        
        draw_list = imgui.get_window_draw_list()
        
        for universe in self.app.universes:
            for fixture in universe.fixtures:
                # Simple tile drawing
                imgui.push_id(str(fixture))
                
                # Color calculation
                color = self._get_fixture_color(fixture)
                col_u32 = imgui.get_color_u32(color)
                
                # Draw Rect
                p_min = imgui.get_cursor_screen_pos()
                p_max = imgui.ImVec2(p_min.x + tile_size, p_min.y + tile_size)
                draw_list.add_rect_filled(p_min, p_max, col_u32)
                
                # Selection logic
                if imgui.invisible_button("##btn", imgui.ImVec2(tile_size, tile_size)):
                    if imgui.get_io().key_ctrl:
                        if fixture in self.app.selected_fixtures:
                            self.app.selected_fixtures.remove(fixture)
                        else:
                            self.app.selected_fixtures.append(fixture)
                    else:
                        self.app.selected_fixtures = [fixture]

                # Highlight selected
                if fixture in self.app.selected_fixtures:
                    draw_list.add_rect(p_min, p_max, imgui.get_color_u32(imgui.ImVec4(1, 1, 0, 1)), 0.0, 0, 2.0)

                # Text
                # Determine text color based on background luminance
                luminance = 0.299 * color.x + 0.587 * color.y + 0.114 * color.z
                text_col = 0xFFFFFFFF if luminance < 0.5 else 0xFF000000
                draw_list.add_text(imgui.ImVec2(p_min.x + 2, p_min.y + 2), text_col, str(fixture.start_address))
                
                imgui.pop_id()
                imgui.next_column()
        
        imgui.columns(1)

    def _get_fixture_color(self, fixture: ActiveFixture) -> imgui.ImVec4:
        r, g, b = 0.0, 0.0, 0.0
        has_color = False
        if "red" in fixture.profile.channel_map:
            r = int(fixture.red) / 255.0
            has_color = True
        if "green" in fixture.profile.channel_map:
            g = int(fixture.green) / 255.0
            has_color = True
        if "blue" in fixture.profile.channel_map:
            b = int(fixture.blue) / 255.0
            has_color = True
        
        intensity = 1.0
        if "intensity" in fixture.profile.channel_map:
            intensity = int(fixture.intensity) / 255.0
            
        if has_color:
            return imgui.ImVec4(r * intensity, g * intensity, b * intensity, 1.0)
        else:
            return imgui.ImVec4(intensity, intensity, intensity, 1.0)


class StageviewWindow(TexturedWindow):
    def __init__(self, app: "App"):
        super().__init__("Stageview", 0.9, "stage.png")
        self.app = app
        self.is_dragging = False
        self.drag_start_map = {}

    def _draw_parametric_background(self):
        draw_list = imgui.get_window_draw_list()
        pos = imgui.get_window_pos()
        size = imgui.get_window_size()
        config = self.app.stage_config

        stage_color = imgui.get_color_u32(imgui.ImVec4(0.15, 0.15, 0.15, 1.0))
        house_color = imgui.get_color_u32(imgui.ImVec4(0.1, 0.1, 0.1, 1.0))
        balcony_color = imgui.get_color_u32(imgui.ImVec4(0.08, 0.08, 0.08, 1.0))
        line_color = imgui.get_color_u32(imgui.ImVec4(0.3, 0.3, 0.3, 1.0))

        stage_top_y = pos.y
        stage_bottom_y = pos.y + size.y * config.stage_area_height
        balcony_top_y = pos.y + size.y * (1.0 - config.balcony_depth)
        balcony_bottom_y = pos.y + size.y
        house_top_y = stage_bottom_y
        house_bottom_y = balcony_top_y if config.has_balcony else balcony_bottom_y

        if config.has_house:
            draw_list.add_rect_filled(
                imgui.ImVec2(pos.x, house_top_y), 
                imgui.ImVec2(pos.x + size.x, house_bottom_y), 
                house_color
            )

        if config.has_house and config.has_balcony:
            draw_list.add_rect_filled(
                imgui.ImVec2(pos.x, balcony_top_y),
                imgui.ImVec2(pos.x + size.x, balcony_bottom_y),
                balcony_color,
            )

        draw_list.add_rect_filled(
            imgui.ImVec2(pos.x, stage_top_y), 
            imgui.ImVec2(pos.x + size.x, stage_bottom_y), 
            stage_color
        )

        num_electrics = config.num_default_electrics
        if num_electrics > 0:
            electric_area_height_px = size.y * config.stage_area_height
            for i in range(1, num_electrics + 1):
                y_pos = pos.y + (i / (num_electrics + 1)) * electric_area_height_px
                x_start = pos.x + size.x * config.electric_padding
                x_end = pos.x + size.x * (1.0 - config.electric_padding)
                draw_list.add_line(
                    imgui.ImVec2(x_start, y_pos), imgui.ImVec2(x_end, y_pos), line_color, 2.0
                )

    def draw_content(self):
        if self.app.stage_config.map_mode == StageConfig.MapMode.GRID:
            self._draw_parametric_background()

        draw_list = imgui.get_window_draw_list()
        w_pos = imgui.get_window_pos()
        w_size = imgui.get_window_size()
        
        # Draw fixtures
        for universe in self.app.universes:
            for fix in universe.fixtures:
                cx = w_pos.x + fix.stagepos[0] * w_size.x
                cy = w_pos.y + fix.stagepos[1] * w_size.y
                
                # Get fixture color logic (similar to Gridview)
                r, g, b = 0.0, 0.0, 0.0
                has_color = False
                if "red" in fix.profile.channel_map:
                    r = int(fix.red) / 255.0
                    has_color = True
                if "green" in fix.profile.channel_map:
                    g = int(fix.green) / 255.0
                    has_color = True
                if "blue" in fix.profile.channel_map:
                    b = int(fix.blue) / 255.0
                    has_color = True
                intensity = 1.0
                if "intensity" in fix.profile.channel_map:
                    intensity = int(fix.intensity) / 255.0
                
                if has_color:
                    col = imgui.ImVec4(r * intensity, g * intensity, b * intensity, 1.0)
                else:
                    col = imgui.ImVec4(intensity, intensity, intensity, 1.0)

                # Simple circle
                draw_list.add_circle_filled(imgui.ImVec2(cx, cy), 10, imgui.get_color_u32(col))
                
                if fix in self.app.selected_fixtures:
                    draw_list.add_circle(imgui.ImVec2(cx, cy), 12, 0xFF00FFFF, 0, 2.0)
                
                # Draw text
                text = str(fix.start_address)
                text_size = imgui.calc_text_size(text)
                luminance = 0.299 * col.x + 0.587 * col.y + 0.114 * col.z
                text_col = 0xFFFFFFFF if luminance < 0.5 else 0xFF000000
                draw_list.add_text(imgui.ImVec2(cx - text_size.x/2, cy - text_size.y/2), text_col, text)

                imgui.set_cursor_screen_pos(imgui.ImVec2(cx - 10, cy - 10))
                imgui.push_id(str(id(fix)))
                imgui.invisible_button("fix", imgui.ImVec2(20, 20))
                
                if imgui.is_item_active() and imgui.is_mouse_dragging(0):
                    if not self.is_dragging:
                        self.is_dragging = True
                        self.drag_start_map = {f: f.stagepos for f in self.app.selected_fixtures}
                        if fix not in self.app.selected_fixtures:
                            self.app.selected_fixtures = [fix]
                            self.drag_start_map = {fix: fix.stagepos}
                    
                    delta = imgui.get_mouse_drag_delta(0)
                    for f, start in self.drag_start_map.items():
                        nx = start[0] + delta.x / w_size.x
                        ny = start[1] + delta.y / w_size.y
                        f.stagepos = (max(0, min(1, nx)), max(0, min(1, ny)))
                
                elif imgui.is_item_clicked():
                    if not imgui.get_io().key_ctrl:
                        self.app.selected_fixtures = [fix]
                    else:
                        if fix in self.app.selected_fixtures:
                            self.app.selected_fixtures.remove(fix)
                        else:
                            self.app.selected_fixtures.append(fix)
                
                imgui.pop_id()

        if not imgui.is_mouse_down(0):
            self.is_dragging = False


@dataclass
class Command:
    name: str
    handler: Callable
    description: str = ""

class CommanderWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Commander")
        self.app = app
        self.input_buf = ""
        self.history = []
        self.commands = self._build_commands()

    def _build_commands(self):
        return {
            "clear": Command("clear", lambda a: self.app.selected_fixtures.clear(), "Clear selection"),
            "select all": Command("select all", lambda a: setattr(self.app, 'selected_fixtures', [f for u in self.app.universes for f in u.fixtures]), "Select All"),
        }

    def draw_content(self):
        # History
        imgui.begin_child("History", imgui.ImVec2(0, -30))
        for h in self.history:
            imgui.text(h)
        imgui.end_child()

        # Input
        imgui.push_item_width(-1)
        entered, self.input_buf = imgui.input_text("##cmd", self.input_buf, imgui.InputTextFlags_.enter_returns_true)
        imgui.pop_item_width()
        
        # Auto-focus
        if imgui.is_window_focused() and not imgui.is_any_item_active():
            imgui.set_keyboard_focus_here(-1)

        if entered and self.input_buf:
            self.history.append(f"> {self.input_buf}")
            self._exec(self.input_buf)
            self.input_buf = ""

    def _exec(self, cmd_str: str):
        parts = cmd_str.split()
        if not parts: return
        cmd_name = parts[0].lower()
        if cmd_name in self.commands:
            try:
                res = self.commands[cmd_name].handler(parts[1:])
                if res: self.history.append(str(res))
            except Exception as e:
                self.history.append(f"Error: {e}")
        else:
            self.history.append("Unknown command")


class LayersWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Layers")
        self.app = app
        self.new_layer_name = ""

    def draw_content(self):
        _, self.new_layer_name = imgui.input_text("Name", self.new_layer_name)
        imgui.same_line()
        if imgui.button("Add Layer") and self.new_layer_name:
            if not self.app.get_show_layer(self.new_layer_name):
                self.app.add_show_layer(self.new_layer_name)
                self.new_layer_name = ""

        imgui.separator()
        
        if imgui.begin_table("layers", 3, flags=imgui.TableFlags_.borders):
            imgui.table_setup_column("Name")
            imgui.table_setup_column("Priority")
            imgui.table_setup_column("Action")
            imgui.table_headers_row()

            to_remove = None
            for layer in self.app.layers:
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text(layer.name)
                imgui.table_next_column()
                imgui.push_item_width(-1)
                changed, layer.priority = imgui.slider_float(f"##p_{layer.name}", layer.priority, 0.0, 1.0)
                if changed:
                    for u in self.app.universes:
                        for f in u.fixtures: f.compose()
                imgui.pop_item_width()
                imgui.table_next_column()
                if imgui.button(f"Del##{layer.name}"):
                    to_remove = layer.name
            
            if to_remove:
                self.app.remove_show_layer(to_remove)
            
            imgui.end_table()


class FaderWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Faders")
        self.app = app

    def draw_content(self):
        if not self.app.selected_fixtures:
            imgui.text("No fixtures selected")
            return
        
        # Just show faders for the first selected fixture's channels for simplicity in this demo
        fix = self.app.selected_fixtures[0]
        layer = fix.layers[self.app.active_layer_name]
        
        avail_x = imgui.get_content_region_avail().x
        width = 40
        cols = max(1, int(avail_x / width))
        imgui.columns(cols, "faders", False)

        for ch_name in fix.profile.channel_map:
            val = getattr(layer, ch_name, 0)
            changed, new_val = imgui.v_slider_int(f"##{ch_name}", imgui.ImVec2(30, 150), int(val), 0, 255, "")
            if changed:
                setattr(layer, ch_name, new_val)
            imgui.text(ch_name[:4])
            imgui.next_column()
        
        imgui.columns(1)


class MasterWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Master")
        self.app = app
        self.level = 255

    def draw_content(self):
        changed, self.level = imgui.v_slider_int("##Master", imgui.ImVec2(50, imgui.get_content_region_avail().y - 20), self.level, 0, 255)
        if changed:
            for f in self.app.selected_fixtures:
                if "intensity" in f.profile.channel_map:
                    setattr(f.layers[self.app.active_layer_name], "intensity", self.level)


class StageConfigWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Stage Config")
        self.app = app
        self.is_open = False

    def draw_content(self):
        imgui.text("Stage configuration settings here...")


# --- Main App Class ---

@dataclass
class StageConfig:
    class MapMode(Enum):
        IMAGE = auto()
        GRID = auto()
    map_mode: MapMode = MapMode.GRID
    num_default_electrics: int = 4
    has_house: bool = True
    has_balcony: bool = False
    balcony_depth: float = 0.2
    stage_area_height: float = 0.5
    electric_padding: float = 0.1


class App:
    def __init__(self, window: Any, renderer: GlfwRenderer, ctx: moderngl.Context):
        self.window = window
        self.renderer = renderer
        self.ctx = ctx
        
        # Data
        self.layers: List[ShowLayer] = [ShowLayer("manual", 1.0), ShowLayer("cues", 1.0)]
        self.universes: List[DMXUniverse] = []
        self.selected_fixtures: List[ActiveFixture] = []
        self.stage_config = StageConfig()
        self.channel_type = ChannelType.INTENSITY
        self.active_layer_name = "manual"

        # Windows
        self.universes_window = UniversesWindow(self)
        self.patch_window = PatchWindow(self)
        self.gridview_window = GridviewWindow(self)
        self.stageview_window = StageviewWindow(self)
        self.commander_window = CommanderWindow(self)
        self.fader_window = FaderWindow(self)
        self.layers_window = LayersWindow(self)
        self.master_window = MasterWindow(self)
        self.stage_config_window = StageConfigWindow(self)
        #self.viz_window = VizWindow(self, ctx)

        self.windows: List[Window] = [
            self.universes_window,
            self.patch_window,
            self.gridview_window,
            self.stageview_window,
            self.stage_config_window,
            self.commander_window,
            self.fader_window,
            self.layers_window,
            self.master_window,
            #self.viz_window,
            ImguiAboutWindow(),
        ]
        
        self.layout_initialized = False

    def get_show_layer(self, name: str) -> Optional[ShowLayer]:
        for layer in self.layers:
            if layer.name == name: return layer
        return None

    def add_show_layer(self, name: str, priority: float = 1.0):
        if self.get_show_layer(name): return
        self.layers.append(ShowLayer(name, priority))
        for u in self.universes:
            for f in u.fixtures:
                if name not in f.layers:
                    f.layers._layers[name] = Layer(name, f.profile, f)

    def remove_show_layer(self, name: str):
        l = self.get_show_layer(name)
        if l:
            self.layers.remove(l)
            for u in self.universes:
                for f in u.fixtures:
                    if name in f.layers: del f.layers[name]

    def update_universes(self):
        for u in self.universes: u.update()

    def draw(self):
        self.update_universes()
        
        # --- 1. Setup Dockspace ---
        viewport = imgui.get_main_viewport()
        imgui.set_next_window_pos(viewport.pos)
        imgui.set_next_window_size(viewport.size)
        imgui.set_next_window_viewport(viewport.id_)
        
        # Window flags for the dockspace host window
        window_flags = imgui.WindowFlags_.no_docking | imgui.WindowFlags_.no_title_bar | \
                       imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.no_resize | \
                       imgui.WindowFlags_.no_move | imgui.WindowFlags_.no_bring_to_front_on_focus | \
                       imgui.WindowFlags_.no_nav_focus | imgui.WindowFlags_.menu_bar

        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        
        
        imgui.pop_style_var(3)

        # Submit the DockSpace
        io = imgui.get_io()
        if io.config_flags & imgui.ConfigFlags_.docking_enable:
            dockspace_id = imgui.dock_space_over_viewport()

            # --- 2. Initialize Layout (Once) ---
            if not self.layout_initialized:
                self._setup_layout(dockspace_id)
                self.layout_initialized = True

        self.draw_main_menu_bar()

        # --- 3. Draw Windows ---
        for w in self.windows:
            w.draw()

    def _setup_layout(self, dockspace_id):

        dock_id_main = dockspace_id
        
        dock_id_left = imgui.internal.dock_builder_split_node(dock_id_main, imgui.Dir.left, 0.20)
        dock_id_right = imgui.internal.dock_builder_split_node(dock_id_main, imgui.Dir.right, 0.25)
        dock_id_down = imgui.internal.dock_builder_split_node(dock_id_main, imgui.Dir.down, 0.30)
        dock_id_center = dock_id_main

        imgui.internal.dock_builder_dock_window("Universes", dock_id_down.id_at_opposite_dir)
        imgui.internal.dock_builder_dock_window("Patch", dock_id_left.id_at_dir)
        
        imgui.internal.dock_builder_dock_window("Layers", dock_id_down.id_at_opposite_dir)
        imgui.internal.dock_builder_dock_window("Master", dock_id_right.id_at_dir)
        
        imgui.internal.dock_builder_dock_window("Faders", dock_id_down.id_at_opposite_dir)
        imgui.internal.dock_builder_dock_window("Commander", dock_id_down.id_at_dir)
        
        imgui.internal.dock_builder_dock_window("Stageview", dock_id_center)
        imgui.internal.dock_builder_dock_window("Gridview", dock_id_center)
        imgui.internal.dock_builder_dock_window("Viz", dock_id_center)

        imgui.internal.dock_builder_finish(dockspace_id)


    def draw_main_menu_bar(self):
        if imgui.begin_menu_bar():
            if imgui.begin_menu("File"):
                if imgui.menu_item("Stage Configuration...", "", False)[0]:
                    self.stage_config_window.is_open = True
                if imgui.menu_item("Exit", "Ctrl+Q", False)[0]:
                    import glfw
                    glfw.set_window_should_close(self.window, True)
                imgui.end_menu()

            if imgui.begin_menu("View"):
                for w in self.windows:
                    _, w.is_open = imgui.menu_item(w.title, "", w.is_open)
                imgui.end_menu()
                
            if imgui.begin_menu("Layout"):
                if imgui.menu_item("Reset Layout", "", False)[0]:
                    self.layout_initialized = False
                imgui.end_menu()

            imgui.end_menu_bar()

    def add_window(self, window: Window) -> int:
        if window not in self.windows:
            self.windows.append(window)
            return len(self.windows) - 1
        raise ValueError("Already added this window!")

    def remove_window(self, window: int | Window) -> Window | None:
        if isinstance(window, int):
            return self.windows.pop(window)
        else:
            self.windows.remove(window)
            return window