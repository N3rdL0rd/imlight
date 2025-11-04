"""
Fixture definitions for Electronic Theatre Controls, Inc. products.
"""

from . import FixtureProfile, ChannelDefinition, ChannelType

COLORSOURCE_SPOT_V = FixtureProfile(
    manufacturer="ETC",
    model="ColorSource Spot V (Stn)",
    channels=(
        ChannelDefinition("intensity", ChannelType.INTENSITY, 0),
        ChannelDefinition("red", ChannelType.RED, 1),
        ChannelDefinition("green", ChannelType.GREEN, 2),
        ChannelDefinition("blue", ChannelType.BLUE, 3),
        ChannelDefinition("strobe", ChannelType.STROBE, 4),
        ChannelDefinition("fan", ChannelType.FAN, 5),
    )
)

COLORSOURCE_SPOT_V_DIRECT = FixtureProfile(
    manufacturer="ETC",
    model="ColorSource Spot V (Dir)",
    channels=(
        ChannelDefinition("intensity", ChannelType.INTENSITY, 0),
        ChannelDefinition("red", ChannelType.RED, 1),
        ChannelDefinition("green", ChannelType.GREEN, 2),
        ChannelDefinition("blue", ChannelType.BLUE, 3),
        ChannelDefinition("indigo", ChannelType.INDIGO, 4),
        ChannelDefinition("lime", ChannelType.LIME, 5),
        ChannelDefinition("strobe", ChannelType.STROBE, 6),
        ChannelDefinition("fan", ChannelType.FAN, 7),
    )
)

COLORSOURCE_FRESNEL_V = FixtureProfile(
    manufacturer="ETC",
    model="ColorSource Fresnel V (Stn)",
    channels=(
        ChannelDefinition("intensity", ChannelType.INTENSITY, 0),
        ChannelDefinition("red", ChannelType.RED, 1),
        ChannelDefinition("green", ChannelType.GREEN, 2),
        ChannelDefinition("blue", ChannelType.BLUE, 3),
        ChannelDefinition("strobe", ChannelType.STROBE, 4),
        ChannelDefinition("zoom", ChannelType.ZOOM, 5),
        ChannelDefinition("fan", ChannelType.FAN, 6),
    )
)

COLORSOURCE_FRESNEL_V_DIRECT = FixtureProfile(
    manufacturer="ETC",
    model="ColorSource Fresnel V (Dir)",
    channels=(
        ChannelDefinition("intensity", ChannelType.INTENSITY, 0),
        ChannelDefinition("red", ChannelType.RED, 1),
        ChannelDefinition("green", ChannelType.GREEN, 2),
        ChannelDefinition("blue", ChannelType.BLUE, 3),
        ChannelDefinition("indigo", ChannelType.INDIGO, 4),
        ChannelDefinition("lime", ChannelType.LIME, 5),
        ChannelDefinition("strobe", ChannelType.STROBE, 6),
        ChannelDefinition("zoom", ChannelType.ZOOM, 7),
        ChannelDefinition("fan", ChannelType.FAN, 8),
    )
)

