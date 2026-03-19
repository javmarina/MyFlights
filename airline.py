from collections import namedtuple
import csv
import os

Airline = namedtuple("Airline", ["name", "alias", "iata", "icao", "callsign", "country", "active"])

airlines = {}


def parse_airlines():
    with open(os.path.join("openflights", "airlines.dat"), "rt", encoding="utf-8") as f:
        for row in csv.reader(f.readlines(), quotechar='"', delimiter=',',
                            quoting=csv.QUOTE_ALL, skipinitialspace=True):
            # 324,"All Nippon Airways","ANA All Nippon Airways","NH","ANA","ALL NIPPON","Japan","Y"
            id, name, alias, iata, icao, callsign, country, active = row
            if active != "Y":
                continue
            airlines[iata] = Airline(name=name, alias=alias, iata=iata, icao=icao, callsign=callsign,
                                    country=country, active=active == "Y")


def airline_by_iata(iata: str) -> Airline:
    if len(airlines) == 0:
        parse_airlines()
    return airlines[iata]
