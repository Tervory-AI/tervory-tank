"""Readable labels for stored measurements; original source fields stay intact."""
from decimal import Decimal
import re

from feeds.geo import area_label


def observation_label(point: dict) -> str:
    title = point["title"]
    place = area_label(point["geo"], point["geo_level"], title)
    if title == "Active listings in unmatched":
        return "Active listings with no matched county"
    for prefix, label in (("PRCP in ", "Precipitation in "), ("TAVG in ", "Average temperature in ")):
        if title.startswith(prefix):
            return label + place
    if point["geo_level"] == "state":
        title = title.replace(f' in {point["geo"]}', f" in {place}")
    category = re.fullmatch(r"([0-9]+) checks in (.+)", title)
    if category:
        return f"Checks in {category[2]} (source category {category[1]})"
    return title.replace("Active listings of type ", "Active listings in source category ")


def unit_label(value: str, unit: str) -> str:
    forms = {
        "listings": ("listing", "listings"),
        "checks": ("check", "checks"),
        "holders": ("holder", "holders"),
        "persons": ("person", "people"),
        "people": ("person", "people"),
        "dollars": ("US dollar", "US dollars"),
        "dollars per gallon": ("US dollar per gallon", "US dollars per gallon"),
        "inches": ("inch", "inches"),
        "degrees F": ("degree Fahrenheit", "degrees Fahrenheit"),
        "TEU": ("20-foot container unit", "20-foot container units"),
        "USD/metric ton": ("US dollar per metric ton", "US dollars per metric ton"),
        "USD/kg": ("US dollar per kilogram", "US dollars per kilogram"),
    }
    singular, plural = forms.get(unit, (unit, unit))
    return singular if abs(Decimal(str(value))) == 1 else plural
