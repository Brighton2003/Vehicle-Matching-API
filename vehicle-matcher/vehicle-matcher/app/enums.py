"""Domain vocabulary shared by the database, schemas and matching logic."""
from enum import Enum


class Transmission(str, Enum):
    AUTOMATIC = "Automatic"
    MANUAL = "Manual"


class BodyType(str, Enum):
    HATCHBACK = "Hatchback"
    SEDAN = "Sedan"
    SUV = "SUV"
    BAKKIE = "Bakkie"
    COUPE = "Coupe"
    MINIVAN = "Minivan"


class FuelType(str, Enum):
    PETROL = "Petrol"
    DIESEL = "Diesel"
    HYBRID = "Hybrid"
    ELECTRIC = "Electric"


# Free-text variations people (or other systems) commonly use -> canonical value.
# Keys are lower-case with whitespace/hyphens/underscores stripped.
TRANSMISSION_ALIASES = {
    "auto": Transmission.AUTOMATIC,
    "automatic": Transmission.AUTOMATIC,
    "at": Transmission.AUTOMATIC,
    "cvt": Transmission.AUTOMATIC,
    "dct": Transmission.AUTOMATIC,
    "tiptronic": Transmission.AUTOMATIC,
    "manual": Transmission.MANUAL,
    "stick": Transmission.MANUAL,
    "mt": Transmission.MANUAL,
}

BODY_TYPE_ALIASES = {
    "hatchback": BodyType.HATCHBACK,
    "hatch": BodyType.HATCHBACK,
    "sedan": BodyType.SEDAN,
    "saloon": BodyType.SEDAN,
    "suv": BodyType.SUV,
    "crossover": BodyType.SUV,
    "bakkie": BodyType.BAKKIE,
    "pickup": BodyType.BAKKIE,
    "truck": BodyType.BAKKIE,
    "coupe": BodyType.COUPE,
    "minivan": BodyType.MINIVAN,
    "mpv": BodyType.MINIVAN,
    "van": BodyType.MINIVAN,
}

FUEL_TYPE_ALIASES = {
    "petrol": FuelType.PETROL,
    "gas": FuelType.PETROL,
    "gasoline": FuelType.PETROL,
    "diesel": FuelType.DIESEL,
    "hybrid": FuelType.HYBRID,
    "electric": FuelType.ELECTRIC,
    "ev": FuelType.ELECTRIC,
}


def text_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def normalise(value: object, aliases: dict, enum_cls: type[Enum]):
    """Return the canonical enum member for a user-supplied string, or None."""
    if isinstance(value, enum_cls):
        return value
    if not isinstance(value, str):
        return None
    return aliases.get(text_key(value))
