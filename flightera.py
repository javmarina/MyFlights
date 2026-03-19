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

            div_past_flights = self.wait_and_find_presence(By.XPATH, "//div[normalize-space()='PAST FLIGHTS']")
            parent_div = div_past_flights.find_element(By.XPATH, "./..")
            rows = parent_div.find_elements(By.XPATH, ".//tbody/tr")
            details_link = None
            for row in rows:
                tds = row.find_elements(By.XPATH, "./td")
                if len(tds) >= 3 and iata_from in tds[2].text:
                    link_elements = tds[-1].find_elements(By.XPATH, "./a")
                    if link_elements:
                        details_link = link_elements[0]
                        break
            if details_link is None:
                print("[ERROR] No dates found for %s departing from %s in %s" % (flight_number, iata_from, self._browser.current_url))
                return {}
            complete_url = details_link.get_attribute("href")
            url_split = complete_url.split("/")
            new_url = "/".join(url_split[:-1]) + "/" + date.strftime("%Y-%m-%d")
            self._browser.get(new_url)
            print("Went to %s" % new_url)

        time.sleep(2)

        airport_divs = self._browser.find_elements(By.XPATH, ".//div[@class='flex flex-col items-center']")
        if len(airport_divs) != 2:
            print("[ERROR] No airports found in %s" % (self._browser.current_url))
            return {}

        scripts = self._browser.find_elements(By.TAG_NAME, "script")
        json_dict = None
        for script in scripts:
            try:
                parsed = json.loads(script.get_attribute("innerHTML"))
                if isinstance(parsed, dict) and parsed.get("@type", "") == "Flight":
                    json_dict = parsed
                    print("Found it!")
                    break
            except (json.JSONDecodeError, Exception):
                pass
        if json_dict is None:
            print("JSON not found :(")
            return {}
        origin_airport = json_dict["departureAirport"]["iataCode"]
        destination_airport = json_dict["arrivalAirport"]["iataCode"]

        flight_time = self._browser.find_element(By.XPATH, "//div[@itemprop='duration']").text.strip()
        distance_text = self._browser.find_element(By.XPATH, "//div[@itemprop='distance']").text.strip()
        distance_km = float(distance_text.split()[0].rstrip("km").replace(",", ""))

        if origin_airport != iata_from:
            raise Exception("Flight %s departing from %s, but found %s" % (flight_number, iata_from, origin_airport))

        departure_time = self._browser.find_element(By.ID, "depTimeLiveHB").text.strip()
        arrival_time = self._browser.find_element(By.ID, "arrTimeLiveHB").text.strip()

        if "aircraft" in json_dict:
            aircraft_model = json_dict["aircraft"]["manufacturer"]["name"] + " " + json_dict["aircraft"]["name"]
            registration_number = json_dict["aircraft"]["identifier"]
        else:
            aircraft_div = self._browser.find_element(By.XPATH, ".//div[@itemprop='aircraft']")
            aircraft_model = aircraft_div.find_element(By.XPATH, ".//*[@itemprop='model']").text.strip()
            registration_number = aircraft_div.find_element(By.XPATH, ".//*[@itemprop='identifier']").text.strip()

        try:
            div_actual_distance = self._browser.find_element(By.XPATH, ".//div[@itemprop='distance']")
            """
            <div class="text-sm text-slate-600 dark:text-gray-300" itemprop="distance">
            <span class="whitespace-nowrap">
                13,457km  / 8,306mi
                <br>(Direct: 9,579km, +28%)
            </span>
            </div>
            """
            actual_distance = div_actual_distance.text.strip()
            actual_distance_km = float(actual_distance.split()[0].rstrip("km ").replace(",", ""))
        except Exception:
            actual_distance_km = -1.0

        flight_info = {
            "flight_number": flight_number,
            "iata_from": origin_airport,
            "iata_to": destination_airport,
            "date": date.isoformat(),
            "departure_time": departure_time,
            "arrival_time": arrival_time,
            "flight_minutes": humantime2minutes(flight_time),
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

        grid = self._browser.find_element(By.XPATH, ".//div[@class='grid grid-cols-2 md:grid-cols-3 gap-4 text-xs mt-6 bg-gray-50 dark:bg-gray-900/50 p-4 rounded-lg']")

        mapping = {
            "STATUS": "aircraft_status",
            "ICAO IDENTIFIER": "aircraft_icao_id",
            "SEAT CONFIGURATION": "aircraft_seats",
            "MODEL": "aircraft_model",
            "ENGINES": "aircraft_engines",
            "FIRST FLIGHT": "aircraft_first_flight"
        }
        plane_info = {}
        for cell in grid.find_elements(By.XPATH, ".//div[@class='text-center']"):
            content = cell.text.strip()
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
            value = content.splitlines()[1].strip()
            if title == "SEAT CONFIGURATION":
                value = int(value.split()[0])
            elif title == "FIRST FLIGHT":
                first_flight_date = value.split(" (")[0]
                value = datetime.datetime.strptime(first_flight_date, '%b %Y').isoformat()

            plane_info[mapping[title]] = value

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
        return True
