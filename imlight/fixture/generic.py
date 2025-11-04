"""
Generic fixture definitions.
"""

from . import FixtureProfile, ChannelDefinition, ChannelType

RGB_PAR = FixtureProfile(
    manufacturer="Generic",
    model="RGB PAR",
    channels=(
        ChannelDefinition("red", ChannelType.RED, 0),
        ChannelDefinition("green", ChannelType.GREEN, 1),
        ChannelDefinition("blue", ChannelType.BLUE, 2),
    )
)

def make_dimmer(name: str) -> FixtureProfile:
    return FixtureProfile(
        manufacturer="Generic",
        model=name,
        channels=(
            ChannelDefinition("intensity", ChannelType.INTENSITY, 0),
        )
    )

DIMMER = make_dimmer("Dimmer")
FRESNEL = make_dimmer("Fresnel")
SCOOP = make_dimmer("Scoop")
PLUG = make_dimmer("Plug")
HOUSE = make_dimmer("House light")