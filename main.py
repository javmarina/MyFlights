import datetime
import json
import os.path
import traceback

import webbrowser
import os
from export_stats import export_stats_to_json


def generate_report(flights_processed_data):
    # Export stats to JSON
    stats = export_stats_to_json(flights_processed_data, 'stats_data.json')

    # Generate a self-contained report.html with stats data inlined as a JS variable.
    # This means report.html works standalone (no server needed) and is ready to print to PDF.
    with open('stats_viewer.html', 'r', encoding='utf-8') as f:
        html = f.read()
    stats_script = '<script>\nconst STATS_DATA = ' + json.dumps(stats, ensure_ascii=False, default=str) + ';\n</script>'
    standalone_html = html.replace('</head>', stats_script + '\n</head>', 1)
    with open('report.html', 'w', encoding='utf-8') as f:
        f.write(standalone_html)
    print("Self-contained report generated: report.html")
    webbrowser.open('file://' + os.path.abspath('report.html'))


def main():
    from flightera import Bot

    bot = None

    flights_orig_path = "flights.json"
    flights_processed_path = "flights_processed.json"
    with open(flights_orig_path, "rt") as f:
        flight_orig_data = json.load(f)

    if not os.path.exists(flights_processed_path):
        with open(flights_processed_path, "wt") as f:
            f.write("{}\n")

    with open(flights_processed_path, "rt") as f:
        flights_processed_data = json.load(f)

    count_new = 0
    for flight_data in flight_orig_data["flights"]:
        # First, check if this is already processed
        flight_number = flight_data["number"]
        if flight_number == "DY7005":
            print("Skipping DY7005!")
            continue
        if not flight_number:
            print("[ERROR] Flight number empty for flight of %s, skipping..." % (flight_data["date"]))
            continue
        key = flight_number + "-" + flight_data["date"]
        if key in flights_processed_data:
            print("Flight already processed! Skipping...")
            continue
        if "corrected_number" in flight_data:
            flight_number = flight_data["corrected_number"]
        date = datetime.datetime.strptime(flight_data["date"], "%Y/%m/%d")
        print("Processing flight %s of %s..." % (flight_number, flight_data["date"]))
        if date > datetime.datetime.now():
            print("Flight is in the future! Skipping...")
            continue
        try:
            if bot is None:
                bot = Bot()
                bot.run(undetected=True)
            flight_info = bot.get_flight_info(flight_number=flight_number, date=date, iata_from=flight_data["from"],
                                              url=flight_data.get("url", None))
            print(flight_info)
            if len(flight_info) == 0:
                print("No info!")
                continue
            if flight_info["registration_number"] != "Unknown":
                plane_info = bot.get_plane_info(flight_info["registration_number"])
                for k, v in plane_info.items():
                    flight_info[k] = v
            else:
                print("Warning: Aircraft registration unknown, skipping plane info")
            flights_processed_data[key] = flight_info
            # Sort flights by date
            flights_processed_data = {k: v for k, v in sorted(flights_processed_data.items(),
                                                              key=lambda item: datetime.datetime.fromisoformat(item[1]["date"]))}
            with open(flights_processed_path, "wt") as f:
                json.dump(flights_processed_data, f, indent=4)
            count_new += 1
        except Exception as e:
            print("Something failed!")
            print(traceback.format_exc())
            exit(-1)

    if bot is not None:
        bot.close()

    if count_new == 0:
        print("No new flights :(")
    else:
        print("Processed %d new flights!" % (count_new))

    generate_report(flights_processed_data)


if __name__ == '__main__':
    main()
