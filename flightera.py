import datetime
import re
import time
import json
from collections import defaultdict
from typing import Optional

import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def humantime2minutes(s):
    d = {
      'w':      7*24*60,
      'week':   7*24*60,
      'weeks':  7*24*60,
      'd':      24*60,
      'day':    24*60,
      'days':   24*60,
      'h':      60,
      'hr':     60,
      'hour':   60,
      'hours':  60,
    }
    mult_items = defaultdict(lambda: 1)
    mult_items.update(d)

    parts = re.search(r'^(\d+)([^\d]*)', s.lower().replace(' ', ''))
    if parts:
        return int(parts.group(1)) * mult_items[parts.group(2)] + humantime2minutes(re.sub(r'^(\d+)([^\d]*)', '', s.lower()))
    else:
        return 0


class Bot:
    def __init__(self):
        self._browser = None

    def run(self, undetected: bool = False):
        if undetected:
            options = uc.ChromeOptions()
            options.add_argument('--no-first-run --no-service-autorun --password-store=basic')
            options.add_experimental_option('prefs', {
                'credentials_enable_service': False,
                'profile': {
                    'password_manager_enabled': False,
                    'default_content_setting_values.cookies': 2
                }
            })
            self._browser = uc.Chrome(options=options, log_level=1)
        else:
            options = Options()
            options.add_experimental_option("prefs", {"profile.default_content_setting_values.cookies": 2})
            self._browser = webdriver.Chrome(options=options)
        self._browser.maximize_window()

    def get_flight_info(self, flight_number: str, date: datetime.datetime, iata_from: str, url: Optional[str] = None):
        time.sleep(1.0)
        if url is not None:
            self._browser.get(url)
        else:
            url = "https://www.flightera.net/en/flight/%s" % (flight_number)
            self._browser.get(url)
            print("Went to %s" % url)
            time.sleep(1.0)

            self.accept_cookies()

            time.sleep(2.0)

            try:
                operated_by = self._browser.find_element(By.XPATH, "//dd[contains(., 'operated by')]")
                operated_text = operated_by.text.strip()
                flight_number = operated_text.split("flight ")[1]

                url = "https://www.flightera.net/en/flight/%s" % (flight_number)
                self._browser.get(url)
                print("Went to %s" % url)
                time.sleep(1.0)

                self.accept_cookies()

                time.sleep(2.0)
            except Exception as e:
                pass

        time.sleep(2)

        # Extract JSON-LD flight data
        scripts = self._browser.find_elements(By.TAG_NAME, "script")
        json_dict = None
        for script in scripts:
            try:
                parsed = json.loads(script.get_attribute("innerHTML"))
                if isinstance(parsed, dict) and parsed.get("@type", "") == "Flight":
                    json_dict = parsed
                    print("Found Flight JSON-LD!")
                    break
            except (json.JSONDecodeError, Exception):
                pass
        
        if json_dict is None:
            print("JSON-LD Flight data not found :(")
            return {}
        
        origin_airport = json_dict["departureAirport"]["iataCode"]
        destination_airport = json_dict["arrivalAirport"]["iataCode"]

        if origin_airport != iata_from:
            raise Exception("Flight %s departing from %s, but found %s" % (flight_number, iata_from, origin_airport))

        # Parse times from JSON-LD (ISO format)
        departure_time_iso = json_dict.get("departureTime", "")
        arrival_time_iso = json_dict.get("arrivalTime", "")
        
        # Extract time components
        departure_time = ""
        arrival_time = ""
        try:
            if departure_time_iso:
                dt = datetime.datetime.fromisoformat(departure_time_iso.replace('Z', '+00:00'))
                departure_time = dt.strftime("%H:%M")
        except Exception:
            pass
        
        try:
            if arrival_time_iso:
                dt = datetime.datetime.fromisoformat(arrival_time_iso.replace('Z', '+00:00'))
                arrival_time = dt.strftime("%H:%M")
        except Exception:
            pass

        # Parse distance from flightDistance (e.g., "766 km")
        distance_km = 0.0
        try:
            distance_str = json_dict.get("flightDistance", "0 km")
            distance_km = float(distance_str.split()[0].replace(",", ""))
        except Exception:
            pass

        # Try to extract flight duration - first try from JSON-LD, then from page
        flight_minutes = 0
        try:
            # Try to find duration element on the page
            duration_elem = self._browser.find_element(By.XPATH, "//div[@itemprop='duration']")
            flight_time = duration_elem.text.strip()
            flight_minutes = humantime2minutes(flight_time)
        except Exception:
            # If not found, try to calculate from times
            try:
                if departure_time_iso and arrival_time_iso:
                    dep_dt = datetime.datetime.fromisoformat(departure_time_iso.replace('Z', '+00:00'))
                    arr_dt = datetime.datetime.fromisoformat(arrival_time_iso.replace('Z', '+00:00'))
                    flight_minutes = int((arr_dt - dep_dt).total_seconds() / 60)
            except Exception:
                pass

        # Try to get aircraft info from JSON-LD or page
        aircraft_model = "Unknown"
        registration_number = "Unknown"
        
        if "aircraft" in json_dict and json_dict["aircraft"]:
            try:
                aircraft = json_dict["aircraft"]
                if "manufacturer" in aircraft and "name" in aircraft:
                    aircraft_model = aircraft.get("manufacturer", {}).get("name", "") + " " + aircraft.get("name", "")
                registration_number = aircraft.get("identifier", "Unknown")
            except Exception:
                pass
        
        # If not in JSON, try to find on page
        if aircraft_model == "Unknown" or registration_number == "Unknown":
            try:
                aircraft_div = self._browser.find_element(By.XPATH, ".//div[@itemprop='aircraft']")
                if aircraft_model == "Unknown":
                    aircraft_model = aircraft_div.find_element(By.XPATH, ".//*[@itemprop='model']").text.strip()
                if registration_number == "Unknown":
                    registration_number = aircraft_div.find_element(By.XPATH, ".//*[@itemprop='identifier']").text.strip()
            except Exception:
                pass

        # Try to extract actual distance (ground distance vs flight distance)
        actual_distance_km = -1.0
        try:
            div_actual_distance = self._browser.find_element(By.XPATH, ".//div[@itemprop='distance']")
            actual_distance = div_actual_distance.text.strip()
            actual_distance_km = float(actual_distance.split()[0].rstrip("km ").replace(",", ""))
        except Exception:
            actual_distance_km = distance_km  # Use flight distance as fallback

        flight_info = {
            "flight_number": flight_number,
            "iata_from": origin_airport,
            "iata_to": destination_airport,
            "date": date.isoformat(),
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "flight_minutes": flight_minutes,
            "distance_km": distance_km,
            "aircraft_model": aircraft_model,
            "registration_number": registration_number,
            "actual_distance": actual_distance_km,
            "source_url": self._browser.current_url
        }
        return flight_info

    def get_plane_info(self, registration_number: str):
        time.sleep(1.0)
        url = "https://www.flightera.net/en/planes/%s" % (registration_number)
        self._browser.get(url)
        print("Went to %s" % url)
        time.sleep(1.0)

        self.accept_cookies()

        time.sleep(2.0)

        # Try to find the grid with better error handling and retries
        grid = None
        for attempt in range(3):
            try:
                grid = self._browser.find_element(By.XPATH, ".//div[@class='grid grid-cols-2 md:grid-cols-3 gap-4 text-xs mt-6 bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg']")
                if grid:
                    break
            except Exception:
                if attempt < 2:
                    print(f"Grid not found on attempt {attempt + 1}, retrying...")
                    time.sleep(2.0)
                else:
                    print("[ERROR] Could not find aircraft info grid")
                    return {}
        
        if grid is None:
            return {}

        mapping = {
            "STATUS": "aircraft_status",
            "ICAO IDENTIFIER": "aircraft_icao_id",
            "SEAT CONFIGURATION": "aircraft_seats",
            "MODEL": "aircraft_model",
            "ENGINES": "aircraft_engines",
            "FIRST FLIGHT": "aircraft_first_flight"
        }
        plane_info = {}
        try:
            for cell in grid.find_elements(By.XPATH, ".//div[@class='text-center']"):
                content = cell.text.strip()
                if not content:
                    continue
                # Content is a multiline string. The first line is the key in mapping dict
                # The rest is the value of the entry
                found = False
                for key in mapping.keys():
                    if content.startswith(key):
                        found = True
                        break
                if not found:
                    continue

                title = content.splitlines()[0].strip()
                if len(content.splitlines()) < 2:
                    continue
                value = content.splitlines()[1].strip()
                if title == "SEAT CONFIGURATION":
                    try:
                        value = int(value.split()[0])
                    except Exception:
                        pass
                elif title == "FIRST FLIGHT":
                    try:
                        first_flight_date = value.split(" (")[0]
                        value = datetime.datetime.strptime(first_flight_date, '%b %Y').isoformat()
                    except Exception:
                        pass

                plane_info[mapping[title]] = value
        except Exception as e:
            print(f"[ERROR] Failed to parse plane info: {e}")
            return plane_info

        print(plane_info)
        return plane_info

    def close(self):
        if self._browser is not None:
            self._browser.quit()

    def wait_and_find_presence(self, by, value, timeout: float = 2.0):
        WebDriverWait(self._browser, timeout=timeout).until(EC.presence_of_element_located((by, value)))
        elements = self._browser.find_elements(by, value)
        if len(elements) > 1:
            print("[WARNING] More than one element found by '{:s}', value '{:s}'".format(str(by), str(value)))
        return elements[0]

    def accept_cookies(self, timeout: float = 2.0) -> bool:
        assert self._browser is not None
        try:
            consentir_btn = self._browser.find_element(By.XPATH, "//p[contains(., 'Consentir')]")
            consentir_btn.click()
            time.sleep(1.0)
        except Exception:
            pass
        return True
