from slimgui.integrations.glfw import GlfwRenderer
from typing import List, Any, Tuple
from slimgui import imgui

from .fixture import ActiveFixture, DMXUniverse, DRIVERS
from .fixture.all import ALL_FIXTURES
from .window import Window, ImguiAboutWindow

class UniversesWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Universes")
        self.app = app
        self.drivers = [driver.clean_name for driver in DRIVERS]
        self.drivers.append("None")
    
    def pre_draw(self):
        imgui.set_next_window_size((600, 300), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((740, 40), imgui.Cond.FIRST_USE_EVER)

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
                selected_idx = self.drivers.index("None" if universe.driver is None else universe.driver.__class__.clean_name)
                changed, new_idx = imgui.combo(
                    f"##driver_combo_{i}",
                    selected_idx,
                    self.drivers
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
                self.app.universes.pop(universe_to_remove_index)
                
class PatchWindow(Window):
    def __init__(self, app: "App"):
        super().__init__("Patch")
        self.app = app
    
        self.fixture_profiles = ALL_FIXTURES
        self.fixture_names = [f"{f.manufacturer} - {f.model}" for f in self.fixture_profiles]
        
        self.selected_universe_index: int = 0
        self.selected_fixture_index: int = 0
        self.start_address: int = 1
        self.fixture_count: int = 1
        
        self.status_message: str = ""
        self.status_is_error: bool = False

    def pre_draw(self):
        imgui.set_next_window_size((700, 400), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((20, 40), imgui.Cond.FIRST_USE_EVER)
        
    def draw_content(self):
        imgui.text("Add New Fixture(s)")
        imgui.separator()

        if not self.app.universes:
            imgui.text_colored((1, 1, 1, 1), "Please add a universe in the 'Universes' window first.")
            return

        self.selected_universe_index = min(self.selected_universe_index, len(self.app.universes) - 1)
        
        universe_names = [f"Universe {i+1}" for i in range(len(self.app.universes))]
        changed, self.selected_universe_index = imgui.combo(
            "Target Universe", self.selected_universe_index, universe_names
        )

        changed, self.selected_fixture_index = imgui.combo(
            "Fixture Type", self.selected_fixture_index, self.fixture_names
        )
        
        changed, self.start_address = imgui.input_int("Start Address", self.start_address)
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
                imgui.table_setup_column("Addr", flags=imgui.TableColumnFlags.WIDTH_FIXED, init_width_or_weight=40)
                imgui.table_setup_column("Name", flags=imgui.TableColumnFlags.WIDTH_STRETCH, init_width_or_weight=2)
                imgui.table_setup_column("Channels", flags=imgui.TableColumnFlags.WIDTH_FIXED, init_width_or_weight=65)
                imgui.table_setup_column("Actions", flags=imgui.TableColumnFlags.WIDTH_FIXED, init_width_or_weight=60)
                imgui.table_headers_row()

                for fixture in target_universe.fixtures:
                    imgui.table_next_row()
                    imgui.table_next_column()
                    imgui.text(str(fixture.start_address))
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
                    start_address=current_address
                )
                
                target_universe.add_fixture(fixture_to_add)
                
                current_address += fixture_profile.channel_count

            self.status_message = f"Successfully patched {self.fixture_count} fixture(s)."
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

    def pre_draw(self):
        imgui.set_next_window_size((800, 600), imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_pos((20, 480), imgui.Cond.FIRST_USE_EVER)

    def draw_content(self):
        """Draws the grid of all fixtures across all universes."""
        
        # --- CHANGE 1: Make the tiles smaller and square ---
        tile_size = 60
        tile_spacing = 4
        
        available_width = imgui.get_content_region_avail()[0]

        num_columns = max(1, int(available_width / (tile_size + tile_spacing)))
        imgui.columns(num_columns, "fixture_grid", border=False)

        for universe in self.app.universes:
            for fixture in universe.fixtures:
                # Pass the single size value to the draw helper
                self._draw_fixture_tile(fixture, tile_size)
                imgui.next_column()

        imgui.columns(1)

    def _get_fixture_color(self, fixture: ActiveFixture) -> Tuple[float, float, float, float]:
        """
        Intelligently determines the RGBA color for a fixture's tile.
        (This method remains unchanged as its logic is still correct)
        """
        r, g, b = 0.0, 0.0, 0.0
        has_color = False
        
        if "red" in fixture.profile.channel_map: r = fixture.red / 255.0; has_color = True # type: ignore
        if "green" in fixture.profile.channel_map: g = fixture.green / 255.0; has_color = True # type: ignore
        if "blue" in fixture.profile.channel_map: b = fixture.blue / 255.0; has_color = True # type: ignore
            
        intensity = 1.0
        if "intensity" in fixture.profile.channel_map:
            intensity = fixture.intensity / 255.0 # type: ignore
        
        if has_color:
            return (r * intensity, g * intensity, b * intensity, 1.0)
        else:
            return (intensity, intensity, intensity, 1.0)

    def _draw_fixture_tile(self, fixture: ActiveFixture, size: float):
        """
        Draws a compact, single tile representing one fixture.
        - The tile is primarily a color swatch.
        - The address is drawn on top of the swatch.
        - A tooltip on hover reveals the fixture's name and model.
        """
        
        # We push a style to remove the padding within the child window,
        # so the color button can fill the entire space.
        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, (0, 0))
        
        # The child window acts as our tile container.
        imgui.begin_child(f"fixture_{fixture.start_address}", size=(size, size))
        
        start_pos = imgui.get_cursor_screen_pos()
        
        color = self._get_fixture_color(fixture)
        
        imgui.color_button("##color_swatch", color, 
                             flags=imgui.ColorEditFlags.NO_TOOLTIP, 
                             size=(size, size))
        
        draw_list = imgui.get_window_draw_list()
        luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        text_color = imgui.get_color_u32((1,1,1,1)) if luminance < 0.5 else imgui.get_color_u32((0,0,0,1))

        text = f"@{fixture.start_address}"
        padding = 4
        draw_list.add_text((start_pos[0] + padding, start_pos[1] + padding), text_color, text)
        
        imgui.end_child()
        imgui.pop_style_var()

        
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text(f"{fixture.profile.manufacturer}")
            imgui.text(f"{fixture.profile.model}")
            imgui.separator()
            intensity_percent = (fixture.intensity / 255.0) if "intensity" in fixture.profile.channel_map else 1.0 # type: ignore
            imgui.text(f"Intensity: {intensity_percent:.0%}")
            imgui.end_tooltip()
        

class App:
    def __init__(self, window: Any, renderer: GlfwRenderer):
        self.window = window
        self.renderer = renderer
        self.universes_window = UniversesWindow(self)
        self.patch_window = PatchWindow(self)
        self.gridview_window = GridviewWindow(self)
        self.windows: List[Window] = [self.universes_window, self.patch_window, self.gridview_window, ImguiAboutWindow()]
        self.universes: List[DMXUniverse] = []
        
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
                    changed, _ = imgui.menu_item(
                        window.title, 
                        selected=window.is_open
                    )
                    
                    if changed:
                        window.is_open = not window.is_open
                
                imgui.end_menu()
            imgui.end_main_menu_bar()
    
    def remove_window(self, window: int|Window) -> Window|None:
        if isinstance(window, int):
            return self.windows.pop(window)
        else:
            self.windows.remove(window)
            return window