from enum import Enum


class AircraftFamily(Enum):
    UNKNOWN = -1
    A220 = 0
    A300 = 1
    A310 = 2
    A320 = 3
    A330 = 4
    A340 = 5
    A350 = 6
    A380 = 7
    B707 = 8
    B717 = 9
    B727 = 10
    B737 = 11
    B747 = 12
    B757 = 13
    B767 = 14
    B777 = 15
    B787 = 16
    CRJ  = 17


def get_family_from_name(aircraft: str) -> AircraftFamily:
    _FAMILY_MAP = [
        ("220",  AircraftFamily.A220),
        ("310",  AircraftFamily.A310),
        ("318",  AircraftFamily.A320),
        ("319",  AircraftFamily.A320),
        ("320",  AircraftFamily.A320),
        ("321",  AircraftFamily.A320),
        ("330",  AircraftFamily.A330),
        ("340",  AircraftFamily.A340),
        ("350",  AircraftFamily.A350),
        ("380",  AircraftFamily.A380),
        ("300",  AircraftFamily.A300),  # after A330/A340/A350/A380 to avoid false matches
        ("707",  AircraftFamily.B707),
        ("717",  AircraftFamily.B717),
        ("727",  AircraftFamily.B727),
        ("737",  AircraftFamily.B737),
        ("747",  AircraftFamily.B747),
        ("757",  AircraftFamily.B757),
        ("767",  AircraftFamily.B767),
        ("777",  AircraftFamily.B777),
        ("787",  AircraftFamily.B787),
        ("CRJ",  AircraftFamily.CRJ),
    ]
    for substring, family in _FAMILY_MAP:
        if substring in aircraft:
            return family
    return AircraftFamily.UNKNOWN
