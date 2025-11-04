from abc import ABC, abstractmethod
from collections import OrderedDict
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type
import numpy as np

class ChannelType(Enum):
    """Enum for the logical function of a channel."""
    INTENSITY = auto()   # Master dimmer
    RED = auto()         # Red color channel (0-255)
    GREEN = auto()       # Green color channel (0-255)
    BLUE = auto()        # Blue color channel (0-255)
    INDIGO = auto()      # Indigo color channel, on certain ETC fixtures that use the ColorSource V RGB engine in direct mode (0-255)
    LIME = auto()        # Lime color channel, on certain ETC fixtures that use the ColorSource V RGB engine in direct mode (0-255)
    WHITE = auto()       # White color channel, for fixtures that support it as an override (0-255)
    
    PAN = auto()         # Pan movement
    PAN_FINE = auto()    # 16-bit Pan
    TILT = auto()        # Tilt movement
    TILT_FINE = auto()   # 16-bit Tilt
    
    GOBO_WHEEL = auto()  # A wheel with static patterns
    COLOR_WHEEL = auto() # A wheel with fixed colors
    
    STROBE = auto()      # Strobe/shutter effects
    ZOOM = auto()        # Beam angle zoom
    FOCUS = auto()       # Beam focus
    FAN = auto()         # Fan speed
    
    CONTROL = auto()     # Fixture control functions (e.g., reset)

@dataclass(frozen=True)
class ValueMapping:
    """Maps a DMX value range to a meaningful name (e.g., for gobos/colors)."""
    dmx_range: Tuple[int, int]
    name: str

@dataclass(frozen=True)
class ChannelDefinition:
    """Defines a single channel within a fixture's profile."""
    name: str                  # Pythonic name, e.g., "red", "pan", "gobo1"
    channel_type: ChannelType
    relative_offset: int       # 0-indexed offset from fixture start address
    default_value: int = 0
    value_mappings: Optional[List[ValueMapping]] = None # For wheels
    
@dataclass(frozen=True)
class FixtureProfile:
    """The immutable blueprint for a type of lighting fixture."""
    manufacturer: str
    model: str
    channels: Tuple[ChannelDefinition, ...]
    
    channel_count: int = field(init=False)
    channel_map: Dict[str, ChannelDefinition] = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, 'channel_count', len(self.channels))
        channel_map = {ch.name: ch for ch in self.channels}
        object.__setattr__(self, 'channel_map', channel_map)

class Layer:
    """Represents a single layer of DMX values for a fixture."""
    def __init__(self, name: str, profile: "FixtureProfile", owner: "ActiveFixture"):
        self.name = name
        self._profile = profile
        self._owner = owner
        
        self.dmx_values = np.zeros(profile.channel_count, dtype=np.uint8)

    def __setattr__(self, name: str, value: int):
        """Allows setting channel values like `layer.red = 255`."""
        if '_profile' in self.__dict__ and name in self._profile.channel_map:
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
            self._layers[name] = Layer(name, self._owner.profile, self._owner)
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
        
    def __repr__(self) -> str:
        return f"<LayerManager layers={list(self._layers.keys())}>"
        
class ActiveFixture:
    """
    Represents a physical fixture instance whose final output is composed
    from a stack of HTP (Highest Takes Precedence) layers.
    """
    def __init__(self, profile: FixtureProfile, start_address: int, name: Optional[str] = None):
        if not (1 <= start_address <= 512 - profile.channel_count + 1):
            raise ValueError("Fixture does not fit in DMX universe at this address.")
            
        self.profile = profile
        self.start_address = start_address
        
        self.layers = LayerManager(self)
        
        self._final_dmx_values = np.zeros(profile.channel_count, dtype=np.uint8)
        self.compose()
        
        self.name = name if name is not None else profile.model

    def compose(self):
        """
        Composes all active layers using HTP (Highest Takes Precedence) logic
        to generate the final DMX output values for this fixture.
        """
        composed_values = np.zeros_like(self._final_dmx_values)
        
        for layer in self.layers:
            np.maximum(composed_values, layer.dmx_values, out=composed_values)
            
        self._final_dmx_values[:] = composed_values

    def __getattr__(self, name: str) -> int | LayerManager:
        """
        Allows getting the *final composed value* of a channel, e.g., `fixture.red`.
        This is now for read-only inspection of the final output.
        """
        if name in self.profile.channel_map:
            ch_def = self.profile.channel_map[name]
            return int(self._final_dmx_values[ch_def.relative_offset])
        if 'layers' in self.__dict__ and name == 'layers':
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
        return (f"<ActiveFixture model='{self.profile.model}' "
                f"address={self.start_address} layers={layer_names}>")
        
class DMXDriver(ABC):
    """
    Class to represent a backend device driving output from a `DMXUniverse`.
    """
    
    clean_name: str = "Generic (override me!)"
    
    @abstractmethod
    def update(self, rendered: np.ndarray):
        """
        Updates and writes out to the backend of this diver.
        """
        pass

class DebugDMXDriver(DMXDriver):
    
    clean_name: str = "Debug"
    
    def update(self, rendered: np.ndarray):
        print(rendered)
        
DRIVERS: List[Type[DMXDriver]] = [DebugDMXDriver]

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
            raise ValueError(f"Fixture '{fixture.profile.model}' at address {new_fixture_start} "
                             f"exceeds universe limit of 512.")

        for existing_fixture in self.fixtures:
            existing_start = existing_fixture.start_address
            existing_end = existing_start + existing_fixture.profile.channel_count - 1

            if (new_fixture_start <= existing_end) and (new_fixture_end >= existing_start):
                raise ValueError(f"Address conflict! Fixture '{fixture.profile.model}' at {new_fixture_start} "
                                 f"overlaps with '{existing_fixture.profile.model}' at {existing_start}.")
        
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