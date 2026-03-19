"""
Export flight statistics to JSON format for web visualization
"""
from datetime import datetime
from collections import Counter
import json
from typing import Union

import pycountry
import pycountry_convert as pc

from airline import airline_by_iata
from airport import airport_by_iata


# ========== DISPLAY FORMATTING HELPERS ==========

def format_number(num):
    """Format number with thousands separator"""
    if isinstance(num, (int, float)):
        return f"{num:,}"
    return str(num)

def format_percentage(value, total, decimals=1):
    """Calculate and format percentage"""
    if total == 0:
        return "0.0"
    pct = (value / total) * 100
    return f"{pct:.{decimals}f}"

def format_milestone_html(flight):
    """Format flight data as HTML for milestone display"""
    if not flight:
        return None
    return f"{flight['flight_number']} on {flight['date']}<br>{flight['route']} • {flight['aircraft']}"


def human_date(date: Union[str, datetime]) -> str:
    if isinstance(date, str):
        date = datetime.fromisoformat(date)
    return date.strftime("%Y-%m-%d")


def get_country_iso(country_name: str) -> str:
    """Convert country name to ISO code using pycountry"""
    try:
        country = pycountry.countries.search_fuzzy(country_name)[0]
        return country.alpha_2
    except:
        # Fallback for some edge cases
        fallback_map = {
            'Kosovo': 'XK',
            'North Macedonia': 'MK'
        }
        return fallback_map.get(country_name, 'XX')


def get_country_flag(country_name: str) -> str:
    """Convert country name to flag emoji using ISO code"""
    iso_code = get_country_iso(country_name)
    if iso_code == 'XX':
        return '🌐'
    
    # Convert ISO code to flag emoji (offset from regional indicator symbols)
    # Regional indicator symbols start at U+1F1E6 (🇦)
    flag = ''.join(chr(0x1F1E6 + ord(char) - ord('A')) for char in iso_code)
    return flag


def get_continent(country_name: str) -> str:
    """Map country to continent using pycountry_convert"""
    try:
        iso_code = get_country_iso(country_name)
        if iso_code == 'XX':
            return 'Unknown'
        
        continent_code = pc.country_alpha2_to_continent_code(iso_code)
        continent_name = pc.convert_continent_code_to_continent_name(continent_code)
        return continent_name
    except:
        return 'Unknown'


def get_airline_alliance(iata_code: str) -> str:
    """Map airline IATA code to alliance"""
    star_alliance = ['UA', 'LH', 'AC', 'SQ', 'TK', 'NH', 'OS', 'SN', 'LX', 'SK', 'TP', 'SA', 'AV', 'ET', 'TG', 'OZ', 'BR', 'CA', 'ZH', 'MS', 'CM', 'AI']
    skyteam = ['DL', 'AF', 'KL', 'AZ', 'SU', 'MU', 'CZ', 'OK', 'RO', 'UX', 'AR', 'AM', 'KQ', 'ME', 'SV', 'VN', 'MF', 'CI', 'KE']
    oneworld = ['AA', 'BA', 'IB', 'AY', 'QF', 'QR', 'CX', 'JL', 'LA', 'MH', 'RJ', 'AT', 'S7']
    
    if iata_code in star_alliance:
        return 'Star Alliance'
    elif iata_code in skyteam:
        return 'SkyTeam'
    elif iata_code in oneworld:
        return 'Oneworld'
    else:
        return 'None'


def is_boeing(model: str) -> bool:
    """Check if aircraft is Boeing"""
    return 'B7' in model or 'Boeing' in model


def is_airbus(model: str) -> bool:
    """Check if aircraft is Airbus"""
    return 'A3' in model or 'Airbus' in model


def is_widebody(seats: int) -> bool:
    """Determine if aircraft is widebody based on seat count"""
    # Typically widebodies have 200+ seats, but this is approximate
    return seats > 250


def export_stats_to_json(flights_processed_data, output_file='stats_data.json'):
    """Export all statistics to a JSON file for web visualization"""
    
    stats = {}
    
    # Total flights
    stats['total_flights'] = len(flights_processed_data)
    
    # === NEW STATISTICS ===
    
    # Distance statistics
    distances = [v.get("distance_km", 0) for v in flights_processed_data.values() if v.get("distance_km", 0) > 0]
    total_distance = sum(distances)
    stats['total_distance_km'] = round(total_distance, 2)
    stats['total_distance_display'] = format_number(round(total_distance, 2))
    stats['average_distance_km'] = round(total_distance / len(distances), 2) if distances else 0
    stats['average_distance_display'] = format_number(round(total_distance / len(distances), 2)) if distances else "0"
    
    # Distance to moon comparison (384,400 km to moon)
    moon_distance = 384400
    stats['moon_trips'] = round(total_distance / moon_distance, 2)
    
    # Time in the air
    flight_minutes = [v.get("flight_minutes", 0) for v in flights_processed_data.values() if v.get("flight_minutes", 0) > 0]
    total_minutes = sum(flight_minutes)
    stats['total_flight_hours'] = round(total_minutes / 60, 1)
    stats['total_flight_days'] = round(total_minutes / (60 * 24), 2)
    
    # Average speed (km/h)
    if total_minutes > 0 and total_distance > 0:
        stats['average_speed_kmh'] = round((total_distance / total_minutes) * 60, 2)
    else:
        stats['average_speed_kmh'] = 0
    
    # Distance per year
    years_distances = {}
    for v in flights_processed_data.values():
        year = datetime.fromisoformat(v["date"]).year
        distance = v.get("distance_km", 0)
        if distance > 0:
            years_distances[year] = years_distances.get(year, 0) + distance
    
    if years_distances:
        all_years = range(min(years_distances.keys()), max(years_distances.keys()) + 1)
        for year in all_years:
            if year not in years_distances:
                years_distances[year] = 0
        years_distances = dict(sorted(years_distances.items()))
        stats['distance_per_year'] = {
            'labels': list(years_distances.keys()),
            'values': [round(v, 0) for v in years_distances.values()]
        }
    
    # Countries and continents visited
    countries_counter = Counter()
    continents_set = set()
    for v in flights_processed_data.values():
        try:
            airport_from = airport_by_iata(v["iata_from"])
            airport_to = airport_by_iata(v["iata_to"])
            countries_counter[airport_from.country] += 1
            countries_counter[airport_to.country] += 1
            continents_set.add(get_continent(airport_from.country))
            continents_set.add(get_continent(airport_to.country))
        except:
            pass
    
    # Sort by visit count descending
    countries_list = [country for country, _ in countries_counter.most_common()]
    stats['countries_visited'] = {
        'count': len(countries_list),
        'list': [{'name': country, 'flag': get_country_flag(country), 'iso_code': get_country_iso(country), 'visits': countries_counter[country]} for country in countries_list]
    }
    
    continents_list = sorted(list(continents_set))
    stats['continents_visited'] = {
        'count': len(continents_list),
        'list': continents_list
    }
    
    # International vs Domestic flights
    domestic_count = 0
    international_count = 0
    for v in flights_processed_data.values():
        try:
            airport_from = airport_by_iata(v["iata_from"])
            airport_to = airport_by_iata(v["iata_to"])
            if airport_from.country == airport_to.country:
                domestic_count += 1
            else:
                international_count += 1
        except:
            pass
    
    stats['domestic_vs_international'] = {
        'domestic': domestic_count,
        'international': international_count,
        'domestic_percentage': round(domestic_count / (domestic_count + international_count) * 100, 1) if (domestic_count + international_count) > 0 else 0
    }
    
    # Boeing vs Airbus
    boeing_count = sum(1 for v in flights_processed_data.values() if is_boeing(v.get("aircraft_model", "")))
    airbus_count = sum(1 for v in flights_processed_data.values() if is_airbus(v.get("aircraft_model", "")))
    other_count = stats['total_flights'] - boeing_count - airbus_count
    
    stats['boeing_vs_airbus'] = {
        'boeing': boeing_count,
        'airbus': airbus_count,
        'other': other_count,
        'boeing_percentage': round(boeing_count / stats['total_flights'] * 100, 1) if stats['total_flights'] > 0 else 0,
        'airbus_percentage': round(airbus_count / stats['total_flights'] * 100, 1) if stats['total_flights'] > 0 else 0,
        'other_percentage': round(other_count / stats['total_flights'] * 100, 1) if stats['total_flights'] > 0 else 0,
        'boeing_display': f"{boeing_count} ({format_percentage(boeing_count, stats['total_flights'])}%)",
        'airbus_display': f"{airbus_count} ({format_percentage(airbus_count, stats['total_flights'])}%)",
        'other_display': f"{other_count} ({format_percentage(other_count, stats['total_flights'])}%)"
    }
    
    # Widebody vs Narrowbody
    widebody_count = sum(1 for v in flights_processed_data.values() if v.get("aircraft_seats", 0) > 0 and is_widebody(v.get("aircraft_seats", 0)))
    narrowbody_count = sum(1 for v in flights_processed_data.values() if v.get("aircraft_seats", 0) > 0 and not is_widebody(v.get("aircraft_seats", 0)))
    unknown_body_count = sum(1 for v in flights_processed_data.values() if v.get("aircraft_seats", 0) == 0)
    
    stats['widebody_vs_narrowbody'] = {
        'widebody': widebody_count,
        'narrowbody': narrowbody_count,
        'unknown': unknown_body_count,
        'widebody_percentage': round(widebody_count / (widebody_count + narrowbody_count) * 100, 1) if (widebody_count + narrowbody_count) > 0 else 0
    }
    
    # Home airports (most frequent departure/arrival)
    departure_airports = Counter([v["iata_from"] for v in flights_processed_data.values()])
    arrival_airports = Counter([v["iata_to"] for v in flights_processed_data.values()])
    
    stats['home_airports'] = {
        'most_frequent_departure': {
            'iata': departure_airports.most_common(1)[0][0] if departure_airports else None,
            'name': airport_by_iata(departure_airports.most_common(1)[0][0]).name if departure_airports else None,
            'count': departure_airports.most_common(1)[0][1] if departure_airports else 0
        },
        'most_frequent_arrival': {
            'iata': arrival_airports.most_common(1)[0][0] if arrival_airports else None,
            'name': airport_by_iata(arrival_airports.most_common(1)[0][0]).name if arrival_airports else None,
            'count': arrival_airports.most_common(1)[0][1] if arrival_airports else 0
        }
    }
    
    # Airline alliances
    airlines = [v["flight_number"][:2] for v in flights_processed_data.values()]
    alliance_counts = Counter([get_airline_alliance(iata) for iata in airlines])
    
    stats['airline_alliances'] = {
        'star_alliance': alliance_counts.get('Star Alliance', 0),
        'skyteam': alliance_counts.get('SkyTeam', 0),
        'oneworld': alliance_counts.get('Oneworld', 0),
        'none': alliance_counts.get('None', 0)
    }
    
    # Longest gap between flights
    sorted_flights = sorted(flights_processed_data.values(), key=lambda x: datetime.fromisoformat(x["date"]))
    max_gap_days = 0
    max_gap_flight1 = None
    max_gap_flight2 = None
    
    for i in range(len(sorted_flights) - 1):
        date1 = datetime.fromisoformat(sorted_flights[i]["date"])
        date2 = datetime.fromisoformat(sorted_flights[i + 1]["date"])
        gap = (date2 - date1).days
        if gap > max_gap_days:
            max_gap_days = gap
            max_gap_flight1 = sorted_flights[i]
            max_gap_flight2 = sorted_flights[i + 1]
    
    stats['longest_gap'] = {
        'days': max_gap_days,
        'flight_before': {
            'flight_number': max_gap_flight1["flight_number"],
            'date': human_date(max_gap_flight1["date"]),
            'route': f"{max_gap_flight1['iata_from']} → {max_gap_flight1['iata_to']}"
        } if max_gap_flight1 else None,
        'flight_after': {
            'flight_number': max_gap_flight2["flight_number"],
            'date': human_date(max_gap_flight2["date"]),
            'route': f"{max_gap_flight2['iata_from']} → {max_gap_flight2['iata_to']}"
        } if max_gap_flight2 else None
    }
    
    # Fastest turnaround (shortest time between consecutive flights)
    min_gap_hours = float('inf')
    min_gap_flight1 = None
    min_gap_flight2 = None
    
    for i in range(len(sorted_flights) - 1):
        date1 = datetime.fromisoformat(sorted_flights[i]["date"])
        date2 = datetime.fromisoformat(sorted_flights[i + 1]["date"])
        gap_hours = (date2 - date1).total_seconds() / 3600
        
        # Only consider if on same or next day (to avoid counting actual short gaps, not months apart)
        if gap_hours < min_gap_hours and gap_hours < 48:
            min_gap_hours = gap_hours
            min_gap_flight1 = sorted_flights[i]
            min_gap_flight2 = sorted_flights[i + 1]
    
    stats['fastest_turnaround'] = {
        'hours': round(min_gap_hours, 1) if min_gap_hours != float('inf') else None,
        'flight1': {
            'flight_number': min_gap_flight1["flight_number"],
            'date': human_date(min_gap_flight1["date"]),
            'route': f"{min_gap_flight1['iata_from']} → {min_gap_flight1['iata_to']}"
        } if min_gap_flight1 else None,
        'flight2': {
            'flight_number': min_gap_flight2["flight_number"],
            'date': human_date(min_gap_flight2["date"]),
            'route': f"{min_gap_flight2['iata_from']} → {min_gap_flight2['iata_to']}"
        } if min_gap_flight2 else None
    }
    
    # 100th flight milestone
    if len(sorted_flights) >= 100:
        flight_100 = sorted_flights[99]  # 0-indexed
        stats['flight_100'] = {
            'flight_number': flight_100["flight_number"],
            'date': human_date(flight_100["date"]),
            'route': f"{flight_100['iata_from']} → {flight_100['iata_to']}",
            'aircraft': flight_100.get("aircraft_model", "Unknown")
        }
        stats['flight_100_display'] = format_milestone_html(stats['flight_100'])
    else:
        stats['flight_100'] = None
        stats['flight_100_display'] = 'Not yet reached'
    
    # Most recent flight
    if sorted_flights:
        recent_flight = sorted_flights[-1]
        stats['most_recent_flight'] = {
            'flight_number': recent_flight["flight_number"],
            'date': human_date(recent_flight["date"]),
            'route': f"{recent_flight['iata_from']} → {recent_flight['iata_to']}",
            'aircraft': recent_flight.get("aircraft_model", "Unknown")
        }
        stats['most_recent_flight_display'] = format_milestone_html(stats['most_recent_flight'])
    else:
        stats['most_recent_flight'] = None
        stats['most_recent_flight_display'] = None
    
    # First flight ever
    if sorted_flights:
        first_flight = sorted_flights[0]
        stats['first_flight'] = {
            'flight_number': first_flight["flight_number"],
            'date': human_date(first_flight["date"]),
            'route': f"{first_flight['iata_from']} → {first_flight['iata_to']}",
            'aircraft': first_flight.get("aircraft_model", "Unknown")
        }
        stats['first_flight_display'] = format_milestone_html(stats['first_flight'])
    else:
        stats['first_flight'] = None
        stats['first_flight_display'] = None
    
    # === END NEW STATISTICS ===
    
    # Aircraft families
    from aircraft import get_family_from_name
    families = [get_family_from_name(v["aircraft_model"]) for v in flights_processed_data.values()]
    counter_families = Counter(families)
    stats['aircraft_families'] = {
        'labels': [family.name for family, _ in counter_families.most_common()],
        'values': [count for _, count in counter_families.most_common()]
    }
    
    # Unique routes
    routes = []
    for v in flights_processed_data.values():
        airports = [v["iata_from"], v["iata_to"]]
        airports.sort()
        routes.append(tuple(airports))
    counter_routes = Counter(routes)
    stats['unique_routes'] = len(set(routes))
    
    # Enhanced routes with display data
    routes_list = [
        (airport1, airport2, num)
        for (airport1, airport2), num in counter_routes.most_common()
    ]
    max_route_count = routes_list[0][2] if routes_list else 1
    
    stats['routes'] = {
        'items': [
            {
                'route': f"{airport1}<->{airport2}",
                'display_name': f"{airport1} ⇄ {airport2}",
                'count': num,
                'display_count': f"{num} flights" if num != 1 else "1 flight",
                'percentage': round((num / max_route_count) * 100, 1),
                'bar_width': f"{(num / max_route_count) * 100:.1f}%"
            }
            for airport1, airport2, num in routes_list
        ],
        'first_page': [],  # Will be set below
        'page_size': 6,
        'has_more': len(routes_list) > 6
    }
    stats['routes']['first_page'] = stats['routes']['items'][:6]
    
    # Aircraft models
    counter_models = Counter((v["aircraft_model"] for v in flights_processed_data.values()))
    stats['aircraft_models'] = {
        'unique_count': len(counter_models),
        'data': [{'model': model, 'count': num} for model, num in counter_models.most_common()]
    }
    
    # Airports
    airports = [v["iata_from"] for v in flights_processed_data.values()]
    airports += [v["iata_to"] for v in flights_processed_data.values()]
    counter_airports = Counter(airports)
    
    airports_list = [
        {'iata': iata, 'name': airport_by_iata(iata).name, 'count': num}
        for iata, num in counter_airports.most_common()
    ]
    
    stats['airports'] = {
        'unique_count': len(set(airports)),
        'items': airports_list,
        'first_page': airports_list[:6],
        'page_size': 6,
        'has_more': len(airports_list) > 6,
        'data': airports_list  # Keep for backward compatibility
    }
    
    # Airlines
    airlines = [v["flight_number"][:2] for v in flights_processed_data.values()]
    counter_airlines = Counter(airlines)
    stats['airlines'] = {
        'unique_count': len(set(airlines)),
        'labels': [f"{airline_by_iata(iata).name}" for iata, _ in counter_airlines.most_common()],
        'iata_codes': [iata for iata, _ in counter_airlines.most_common()],
        'values': [num for _, num in counter_airlines.most_common()]
    }
    
    # Flight numbers
    flight_numbers = [v["flight_number"] for v in flights_processed_data.values()]
    counter_flight_numbers = Counter(flight_numbers)
    repeated_flights = []
    for flight_number, num in counter_flight_numbers.most_common():
        if num == 1:
            break
        directions = set()
        for v in flights_processed_data.values():
            if v["flight_number"] == flight_number:
                directions.add((v["iata_from"], v["iata_to"]))
        repeated_flights.append({
            'flight_number': flight_number,
            'count': num,
            'directions': [f"{a} → {b}" for (a, b) in directions]
        })
    stats['flight_numbers'] = {
        'unique_count': len(set(flight_numbers)),
        'repeated': repeated_flights
    }
    
    # Flights per year
    years = [datetime.fromisoformat(v["date"]).year for v in flights_processed_data.values()]
    all_years = range(min(years), max(years) + 1)
    counter_years = Counter(years)
    for year in all_years:
        if year not in counter_years:
            counter_years[year] = 0
    counter_years = dict(sorted(counter_years.items()))
    stats['flights_per_year'] = {
        'labels': list(counter_years.keys()),
        'values': list(counter_years.values())
    }
    
    # Flights per month
    months = [datetime.fromisoformat(v["date"]).month for v in flights_processed_data.values()]
    counter_months = Counter(months)
    month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    stats['flights_per_month'] = {
        'labels': [f"{month_names[m-1]}" for m in range(1, 13)],
        'values': [counter_months.get(m, 0) for m in range(1, 13)]
    }
    
    # Top months with most flights
    month_years = [(datetime.fromisoformat(v["date"]).year, datetime.fromisoformat(v["date"]).month) for v in flights_processed_data.values()]
    counter_month_years = Counter(month_years)
    stats['top_months'] = [
        {
            'month': datetime(year=year, month=month, day=1).strftime("%B %Y"),
            'count': count
        }
        for (year, month), count in counter_month_years.most_common(5)
    ]
    
    # Flight durations
    durations = {}
    for k, v in flights_processed_data.items():
        if "flight_minutes" in v and v["flight_minutes"] > 0:
            durations[k] = v["flight_minutes"]
    
    if durations:
        N = min(5, len(durations)//2)
        
        longest_flights = []
        for flight_key in sorted(durations, key=durations.get, reverse=True)[:N]:
            flight = flights_processed_data[flight_key]
            duration = durations[flight_key]
            hours = duration // 60
            minutes = duration % 60
            
            # Get airport coordinates
            try:
                airport_from = airport_by_iata(flight['iata_from'])
                coords_from = [airport_from.lat, airport_from.lon]
            except:
                coords_from = None
                
            try:
                airport_to = airport_by_iata(flight['iata_to'])
                coords_to = [airport_to.lat, airport_to.lon]
            except:
                coords_to = None
            
            longest_flights.append({
                'flight_number': flight["flight_number"],
                'aircraft_model': flight["aircraft_model"],
                'route': f"{flight['iata_from']} → {flight['iata_to']}",
                'coords_from': coords_from,
                'coords_to': coords_to,
                'iata_from': flight['iata_from'],
                'iata_to': flight['iata_to'],
                'date': human_date(flight["date"]),
                'duration_minutes': duration,
                'duration_text': f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            })
        stats['longest_flights'] = longest_flights
        
        # Shortest flights
        shortest_flights = []
        for flight_key in sorted(durations, key=durations.get)[:N]:
            flight = flights_processed_data[flight_key]
            duration = durations[flight_key]
            hours = duration // 60
            minutes = duration % 60
            
            # Get airport coordinates
            try:
                airport_from = airport_by_iata(flight['iata_from'])
                coords_from = [airport_from.lat, airport_from.lon]
            except:
                coords_from = None
                
            try:
                airport_to = airport_by_iata(flight['iata_to'])
                coords_to = [airport_to.lat, airport_to.lon]
            except:
                coords_to = None
            
            shortest_flights.append({
                'flight_number': flight["flight_number"],
                'aircraft_model': flight["aircraft_model"],
                'route': f"{flight['iata_from']} → {flight['iata_to']}",
                'coords_from': coords_from,
                'coords_to': coords_to,
                'iata_from': flight['iata_from'],
                'iata_to': flight['iata_to'],
                'date': human_date(flight["date"]),
                'duration_minutes': duration,
                'duration_text': f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            })
        stats['shortest_flights'] = shortest_flights
        
        # Duration histogram data
        duration_values = list(durations.values())
        max_dur = int(max(duration_values))
        max_edge = ((max_dur + 59) // 60) * 60
        
        # Create bins for histogram
        bin_size = 60  # 60 minutes
        bins = list(range(0, max_edge + bin_size, bin_size))
        histogram = [0] * (len(bins) - 1)
        
        for duration in duration_values:
            for i in range(len(bins) - 1):
                if bins[i] <= duration < bins[i + 1]:
                    histogram[i] += 1
                    break
        
        stats['duration_histogram'] = {
            'labels': [f"{b // 60}h" for b in bins[:-1]],
            'values': histogram
        }
    
    # Plane age statistics
    plane_age = {}
    for k, v in flights_processed_data.items():
        if "aircraft_first_flight" in v:
            plane_age[k] = datetime.fromisoformat(v["date"]) - datetime.fromisoformat(v["aircraft_first_flight"])
    
    if plane_age:
        plane_age_precise = [age.total_seconds() / (365.25 * 24 * 3600) for age in plane_age.values()]
        stats['average_plane_age'] = round(sum(plane_age_precise) / len(plane_age_precise), 2)
        
        # Plane age distribution
        plane_age_years = [age.days // 365 for age in plane_age.values()]
        all_years = range(0, max(plane_age_years) + 1)
        counter_years = Counter(plane_age_years)
        for year in all_years:
            if year not in counter_years:
                counter_years[year] = 0
        counter_years = dict(sorted(counter_years.items()))
        stats['plane_age_distribution'] = {
            'labels': list(counter_years.keys()),
            'values': list(counter_years.values())
        }
        
        # Youngest and oldest plane at time of flight
        youngest_flight_key = min(plane_age, key=plane_age.get)
        youngest_flight = flights_processed_data[youngest_flight_key]
        youngest_age_days = plane_age[youngest_flight_key].days
        
        oldest_flight_key = max(plane_age, key=plane_age.get)
        oldest_flight = flights_processed_data[oldest_flight_key]
        oldest_age_days = plane_age[oldest_flight_key].days
        
        stats['youngest_plane_flight'] = {
            'flight_number': youngest_flight["flight_number"],
            'aircraft_model': youngest_flight["aircraft_model"],
            'route': f"{youngest_flight['iata_from']} → {youngest_flight['iata_to']}",
            'date': human_date(youngest_flight["date"]),
            'age_days': youngest_age_days,
            'age_years': round(youngest_age_days / 365.25, 1)
        }
        
        stats['oldest_plane_flight'] = {
            'flight_number': oldest_flight["flight_number"],
            'aircraft_model': oldest_flight["aircraft_model"],
            'route': f"{oldest_flight['iata_from']} → {oldest_flight['iata_to']}",
            'date': human_date(oldest_flight["date"]),
            'age_days': oldest_age_days,
            'age_years': round(oldest_age_days / 365.25, 1)
        }
        
        # Plane manufacturing years
        plane_age_absolute = {}
        for k, v in flights_processed_data.items():
            if "aircraft_first_flight" in v:
                plane_age_absolute[k] = datetime.fromisoformat(v["aircraft_first_flight"])
        
        years = [date.year for date in plane_age_absolute.values()]
        all_years = range(min(years), max(years) + 1)
        counter_years = Counter(years)
        for year in all_years:
            if year not in counter_years:
                counter_years[year] = 0
        counter_years = dict(sorted(counter_years.items()))
        stats['plane_manufacturing_years'] = {
            'labels': list(counter_years.keys()),
            'values': list(counter_years.values())
        }
        
        # Youngest and oldest plane (absolute)
        youngest_plane_key = max(plane_age_absolute, key=plane_age_absolute.get)
        youngest_plane = flights_processed_data[youngest_plane_key]
        youngest_plane_birth = plane_age_absolute[youngest_plane_key]
        
        oldest_plane_key = min(plane_age_absolute, key=plane_age_absolute.get)
        oldest_plane = flights_processed_data[oldest_plane_key]
        oldest_plane_birth = plane_age_absolute[oldest_plane_key]
        
        stats['youngest_plane_absolute'] = {
            'flight_number': youngest_plane["flight_number"],
            'aircraft_model': youngest_plane["aircraft_model"],
            'route': f"{youngest_plane['iata_from']} → {youngest_plane['iata_to']}",
            'flight_date': human_date(youngest_plane["date"]),
            'birth_date': human_date(youngest_plane_birth)
        }
        
        stats['oldest_plane_absolute'] = {
            'flight_number': oldest_plane["flight_number"],
            'aircraft_model': oldest_plane["aircraft_model"],
            'route': f"{oldest_plane['iata_from']} → {oldest_plane['iata_to']}",
            'flight_date': human_date(oldest_plane["date"]),
            'birth_date': human_date(oldest_plane_birth)
        }
    
    # Repeated aircraft
    reg_numbers = [v["registration_number"] for v in flights_processed_data.values()]
    counter = Counter(reg_numbers)
    repeated_aircraft = []
    for reg_number, count in counter.most_common():
        if count == 1:
            break
        flights = [flight for key, flight in flights_processed_data.items() if flight["registration_number"] == reg_number]
        flights_info = [
            {
                'flight_number': f["flight_number"],
                'route': f"{f['iata_from']} → {f['iata_to']}",
                'date': human_date(f["date"])
            }
            for f in flights
        ]
        repeated_aircraft.append({
            'registration': reg_number,
            'count': count,
            'flights': flights_info
        })
    stats['repeated_aircraft'] = repeated_aircraft
    
    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    
    print(f"Statistics exported to {output_file}")
    return stats
