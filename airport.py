import os
from collections import namedtuple
import csv

Airport = namedtuple("Airport", ["name", "city", "country", "iata", "icao", "lat", "lon", "alt", "tz", "dst", "type", "source"])

airports = {}


def parse_float(s: str) -> float:
    try:
        return float(s)
    except ValueError:
        return float("nan")


def parse_airports():
    with open(os.path.join("openflights", "airports.dat"), "rt", encoding='utf-8') as f:
        for row in csv.reader(f.readlines(), quotechar='"', delimiter=',',
                            quoting=csv.QUOTE_ALL, skipinitialspace=True):
            # 507,"London Heathrow Airport","London","United Kingdom","LHR","EGLL",51.4706,-0.461941,83,0,"E","Europe/London","airport","OurAirports"
            _, name, city, country, iata, icao, lat, lon, alt, _, tz, dst, type, source = row
            airports[iata] = Airport(name=name, city=city, country=country, iata=iata, icao=icao, lat=parse_float(lat),
                                     lon=parse_float(lon), alt=parse_float(alt), tz=tz, dst=dst, type=type,
                                     source=source)


def airport_by_iata(iata: str) -> Airport:
    if len(airports) == 0:
        parse_airports()
    return airports[iata]
