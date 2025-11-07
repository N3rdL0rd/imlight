from __future__ import annotations
from abc import ABC, abstractmethod
from collections import OrderedDict
from enum import Enum, auto
from dataclasses import dataclass, field
import threading
from typing import Any, Dict, List, Optional, Tuple, Type
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type
import numpy as np
import os

if os.name != "nt":
    from ola.ClientWrapper import ClientWrapper
    from ola.OlaClient import OLADNotRunningException

if TYPE_CHECKING:
    from ..app import App

class ChannelType(Enum):
    """Enum for the logical function of a channel."""

    INTENSITY = auto()  # Master dimmer
    RED = auto()  # Red color channel (0-255)
    GREEN = auto()  # Green color channel (0-255)
    BLUE = auto()  # Blue color channel (0-255)
    INDIGO = auto()  # Indigo color channel, on certain ETC fixtures that use the ColorSource V RGB engine in direct mode (0-255)
    LIME = auto()  # Lime color channel, on certain ETC fixtures that use the ColorSource V RGB engine in direct mode (0-255)
    WHITE = (
        auto()
    )  # White color channel, for fixtures that support it as an override (0-255)

    PAN = auto()  # Pan movement
    PAN_FINE = auto()  # 16-bit Pan
    TILT = auto()  # Tilt movement
    TILT_FINE = auto()  # 16-bit Tilt

    GOBO_WHEEL = auto()  # A wheel with static patterns
    COLOR_WHEEL = auto()  # A wheel with fixed colors

    STROBE = auto()  # Strobe/shutter effects
    ZOOM = auto()  # Beam angle zoom
    FOCUS = auto()  # Beam focus
    FAN = auto()  # Fan speed

    CONTROL = auto()  # Fixture control functions (e.g., reset)


@dataclass(frozen=True)
class ValueMapping:
    """Maps a DMX value range to a meaningful name (e.g., for gobos/colors)."""

    dmx_range: Tuple[int, int]
    name: str


@dataclass(frozen=True)
class ChannelDefinition:
    """Defines a single channel within a fixture's profile."""

    name: str  # Pythonic name, e.g., "red", "pan", "gobo1"
    channel_type: ChannelType
    relative_offset: int  # 0-indexed offset from fixture start address
    default_value: int = 0
    value_mappings: Optional[List[ValueMapping]] = None  # For wheels


class IconType(Enum):
    GENERIC = auto()
    FRESNEL = auto()
    SCOOP = auto()
    SPOT = auto()
    HOUSE = auto()

@dataclass(frozen=True)
class FixtureProfile:
    """The immutable blueprint for a type of lighting fixture."""

    manufacturer: str
    model: str
    channels: Tuple[ChannelDefinition, ...]

    icon_type: IconType = IconType.GENERIC
    channel_count: int = field(init=False)
    channel_map: Dict[str, ChannelDefinition] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "channel_count", len(self.channels))
        channel_map = {ch.name: ch for ch in self.channels}
        object.__setattr__(self, "channel_map", channel_map)


@dataclass
class ShowLayer:
    """Represents a global layer's properties, managed by the App."""
    name: str
    priority: float = 1.0


class Layer:
    """Represents a single layer of DMX values for a fixture."""

    def __init__(self, name: str, profile: "FixtureProfile", owner: "ActiveFixture"):
        self.name = name
        self._profile = profile
        self._owner = owner

        self.dmx_values = np.zeros(profile.channel_count, dtype=np.uint8)

    def __setattr__(self, name: str, value: int):
        """Allows setting channel values like `layer.red = 255`."""
        if "_profile" in self.__dict__ and name in self._profile.channel_map:
            if not (0 <= value <= 255):
                raise ValueError("DMX value must be between 0 and 255.")

            ch_def = self._profile.channel_map[name]
            self.dmx_values[ch_def.relative_offset] = np.uint8(value)

            self._owner.compose()
        else:
            super().__setattr__(name, value)

    def __repr__(self) -> str:
        return f"<Layer name='{self.name}'>"


class LayerManager:
    """Provides a dictionary-like interface to manage a fixture's layers."""

    def __init__(self, owner: "ActiveFixture"):
        self._owner = owner
        self._layers: Dict[str, Layer] = OrderedDict()

    def __getitem__(self, name: str) -> Layer:
        """Access a layer by name, creating it if it doesn't exist."""
        if name not in self._layers:
            # If a layer is accessed that doesn't exist, create it on the fixture
            # AND register it as a new global ShowLayer in the app.
            self._layers[name] = Layer(name, self._owner.profile, self._owner)
            self._owner.app.add_show_layer(name)
        return self._layers[name]

    def __delitem__(self, name: str):
        """Remove a layer by name."""
        if name in self._layers:
            del self._layers[name]
            self._owner.compose()
        else:
            raise KeyError(f"Layer '{name}' not found.")

    def __contains__(self, name: str) -> bool:
        return name in self._layers

    def __iter__(self):
        return iter(self._layers.values())
    
    def keys(self):
        return self._layers.keys()

    def __repr__(self) -> str:
        return f"<LayerManager layers={list(self._layers.keys())}>"


class ActiveFixture:
    """
    Represents a physical fixture instance whose final output is composed
    from a stack of HTP (Highest Takes Precedence) layers, each modulated by a
    global priority.
    """

    def __init__(
        self,
        app: "App",
        profile: FixtureProfile,
        start_address: int,
        name: Optional[str] = None,
        start_stagepos: Optional[Tuple[float, float]] = None,
    ):
        if not (1 <= start_address <= 512 - profile.channel_count + 1):
            raise ValueError("Fixture does not fit in DMX universe at this address.")

        self.app = app
        self.profile = profile
        self.start_address = start_address
        self.layers = LayerManager(self)

        for show_layer in self.app.layers:
            self.layers._layers[show_layer.name] = Layer(show_layer.name, self.profile, self)

        self._final_dmx_values = np.zeros(profile.channel_count, dtype=np.uint8)
        self.compose()

        self.name = name if name is not None else profile.model
        self.stagepos: Tuple[float, float] = (
            start_stagepos if start_stagepos is not None else (0.05, 0.05)
        )

    def compose(self):
        """
        Composes all active layers using HTP logic after modulating each layer
        by its global priority.
        """
        composed_values = np.zeros(self.profile.channel_count, dtype=np.float32)

        for layer in self.layers:
            show_layer = self.app.get_show_layer(layer.name)
            if show_layer is None:
                continue # Should not happen in normal operation

            priority = show_layer.priority
            if priority > 0:
                modulated_values = layer.dmx_values.astype(np.float32) * priority
                np.maximum(composed_values, modulated_values, out=composed_values)

        np.clip(composed_values, 0, 255, out=composed_values)
        self._final_dmx_values[:] = composed_values.astype(np.uint8)

    def __getattr__(self, name: str) -> int | LayerManager:
        """
        Allows getting the *final composed value* of a channel, e.g., `fixture.red`.
        This is now for read-only inspection of the final output.
        """
        if name in self.profile.channel_map:
            ch_def = self.profile.channel_map[name]
            return int(self._final_dmx_values[ch_def.relative_offset])
        if "layers" in self.__dict__ and name == "layers":
            return self.layers
        raise AttributeError(f"'{self.profile.model}' has no attribute '{name}'")

    @property
    def dmx_values(self) -> np.ndarray:
        """
        Read-only access to the final, composed DMX values array.
        This is what the DMXUniverse will render.
        """
        return self._final_dmx_values

    def __repr__(self) -> str:
        layer_names = list(self.layers._layers.keys())
        return (
            f"<ActiveFixture model='{self.profile.model}' "
            f"address={self.start_address} layers={layer_names}>"
        )


class DriverError(Exception):
    """Base class for all driver-related errors."""
    pass

class DriverInitError(DriverError):
    """Raised when a DMX driver fails to initialize."""
    pass

class ConfigParameterType(Enum):
    """Defines the type of a configuration parameter for UI generation."""
    INT = auto()
    STRING = auto()
    BOOL = auto()

@dataclass
class ConfigParameter:
    """Defines the schema for a single configuration option for a DMXDriver."""
    name: str
    param_type: ConfigParameterType
    default_value: Any
    description: Optional[str] = None
    constraints: Optional[dict] = field(default_factory=dict)


class DMXDriver(ABC):
    """
    Abstract base class for a DMX output driver.
    """
    clean_name: str = "Generic (override me!)"
    CONFIG_PARAMS: List[ConfigParameter] = []

    def __init__(self):
        """Initializes the driver's config with default values from its schema."""
        self.config = {
            param.name: param.default_value for param in self.CONFIG_PARAMS
        }

    def on_config_changed(self):
        """
        Optional hook called by the UI after self.config has been updated.
        Drivers can use this to re-initialize if necessary.
        """
        pass

    @abstractmethod
    def update(self, rendered: np.ndarray):
        pass

class DebugDMXDriver(DMXDriver):
    clean_name: str = "Debug"

    def update(self, rendered: np.ndarray):
        print(rendered)


TICK_INTERVAL = 25  # in milliseconds (for 40fps)

if os.name != "nt":
    class OlaDMXDriver(DMXDriver):
        """
        A DMX driver that sends data to a universe via the OLA daemon (olad).
        """
        clean_name: str = "OLA"
        CONFIG_PARAMS: List[ConfigParameter] = [
            ConfigParameter(
                name="universe",
                param_type=ConfigParameterType.INT,
                default_value=1,
                description="The OLA universe number to output to (1-indexed).",
                constraints={'min': 1, 'max': 65535}
            )
        ]

        def __init__(self):
            super().__init__()
            self._dmx_data = np.zeros(512, dtype=np.uint8)
            self._lock = threading.Lock()
            self._wrapper: Optional[ClientWrapper] = None
            self._thread: Optional[threading.Thread] = None

        def _ola_tick(self) -> bool:
            """
            Periodically called from the OLA thread to send the latest DMX data.
            """
            with self._lock:
                data_to_send = self._dmx_data.tolist()
                current_universe = self.config.get("universe", 1)

            if self._wrapper:
                self._wrapper.Client().SendDmx(current_universe, data_to_send, self._send_callback)
            
            return True

        @staticmethod
        def _send_callback(status):
            """
            Callback from OLA to report the status of the DMX send operation.
            """
            if not status.Succeeded():
                print(f"Error sending DMX to OLA: {status.message}")

        def on_config_changed(self):
            """
            (Re)starts the OLA client and its background thread.
            This method is designed to be called after __init__ or when config changes.
            """
            if self._wrapper:
                self._wrapper.Stop()
                if self._thread and self._thread.is_alive():
                    self._thread.join()
            
            try:
                self._wrapper = ClientWrapper()
            except OLADNotRunningException:
                raise DriverInitError("Failed to connect to OLA daemon (olad). Please ensure it is running.")

            self._thread = threading.Thread(target=self._wrapper.Run)
            self._thread.daemon = True
            self._thread.start()
            self._wrapper.AddEvent(TICK_INTERVAL, self._ola_tick)

        def update(self, rendered: np.ndarray):
            """
            Called from the main application thread to provide the latest DMX frame.
            """
            with self._lock:
                np.copyto(self._dmx_data, rendered)
                

class FileLogDMXDriver(DMXDriver):
    """
    A test driver that logs DMX frames to a file.
    """
    clean_name: str = "File Logger"
    CONFIG_PARAMS: List[ConfigParameter] = [
        ConfigParameter(
            name="enabled",
            param_type=ConfigParameterType.BOOL,
            default_value=True,
            description="Enable or disable logging."
        ),
        ConfigParameter(
            name="filename",
            param_type=ConfigParameterType.STRING,
            default_value="dmx_log.txt",
            description="The path to the file where DMX frames will be logged."
        ),
        ConfigParameter(
            name="log_interval",
            param_type=ConfigParameterType.INT,
            default_value=1,
            description="Log only every Nth frame to reduce file size.",
            constraints={'min': 1, 'max': 100}
        )
    ]

    def __init__(self):
        super().__init__()
        self._frame_count: int = 0
        self._file_handle: Optional[Any] = None
        self.on_config_changed()

    def on_config_changed(self):
        """Called when config is saved. Re-opens the log file with the new name."""
        # Close the existing file handle if it's open
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        # Open the new file in append mode
        try:
            filename = self.config.get("filename", "dmx_log.txt")
            if filename: # Ensure filename is not empty
                self._file_handle = open(filename, "a")
                print(f"File logger now writing to {filename}")
        except IOError as e:
            print(f"Error opening log file: {e}")
            self._file_handle = None

    def update(self, rendered: np.ndarray):
        """Writes the DMX frame to the file if conditions are met."""
        if not self.config.get("enabled", False) or not self._file_handle:
            return

        self._frame_count += 1
        if self._frame_count % self.config.get("log_interval", 1) == 0:
            active_channels = [f"{i+1}:{val}" for i, val in enumerate(rendered) if val > 0]
            log_line = f"Frame {self._frame_count}: " + ", ".join(active_channels) + "\n"
            self._file_handle.write(log_line)
            self._file_handle.flush() # Ensure it's written immediately

    def __del__(self):
        """Ensure the file is closed when the driver is destroyed."""
        if self._file_handle:
            self._file_handle.close()


DRIVERS: List[Type[DMXDriver]] = [FileLogDMXDriver, DebugDMXDriver]

if os.name != "nt":
    DRIVERS.insert(-2, OlaDMXDriver)


class DMXUniverse:
    def __init__(self, driver: Optional[DMXDriver] = None):
        self.fixtures: List[ActiveFixture] = []
        self._dmx_frame = np.zeros(512, dtype=np.uint8)
        self.driver = driver

    def set_driver(self, driver: DMXDriver):
        self.driver = driver

    def add_fixture(self, fixture: ActiveFixture):
        """Adds a fixture to the universe, checking for address overlaps."""
        new_fixture_start = fixture.start_address
        new_fixture_end = new_fixture_start + fixture.profile.channel_count - 1

        if new_fixture_end > 512:
            raise ValueError(
                f"Fixture '{fixture.profile.model}' at address {new_fixture_start} "
                f"exceeds universe limit of 512."
            )

        for existing_fixture in self.fixtures:
            existing_start = existing_fixture.start_address
            existing_end = existing_start + existing_fixture.profile.channel_count - 1

            if (new_fixture_start <= existing_end) and (
                new_fixture_end >= existing_start
            ):
                raise ValueError(
                    f"Address conflict! Fixture '{fixture.profile.model}' at {new_fixture_start} "
                    f"overlaps with '{existing_fixture.profile.model}' at {existing_start}."
                )

        self.fixtures.append(fixture)
        self.fixtures.sort(key=lambda f: f.start_address)

    def remove_fixture(self, fixture: ActiveFixture):
        self.fixtures.remove(fixture)

    def update(self) -> None:
        """
        Renders and updates all DMX outputs tied to this universe.
        """
        out = self.render()
        if self.driver is not None:
            self.driver.update(out)

    def render(self) -> np.ndarray:
        """
        Generates the final 512-byte DMX frame from all fixture states.
        """
        self._dmx_frame.fill(0)
        for fixture in self.fixtures:
            start = fixture.start_address - 1
            end = start + fixture.profile.channel_count
            self._dmx_frame[start:end] = fixture.dmx_values

        return self._dmx_frame
