#!/usr/bin/env python3
"""
BMW i5 Scraper - Robust version
Extracts all BMW i5 Sedan vehicles from occasions.bmw.nl
Reads filter configuration from config.json
"""

import json
import re
import sys
import time
import base64
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing dependencies. Install with:")
    print("  pip install requests")
    sys.exit(1)

BASE_URL = "https://occasions.bmw.nl/bmw/zoeken/resultaten"
CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config():
    """Load filter configuration from config.json"""
    if not CONFIG_FILE.exists():
        print(f"ERROR: Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return config.get('filters', {})


def build_php_serialized_filters(filters, page_num):
    """Build PHP serialized filter string from config"""
    items = []  # List of key-value pairs

    # Fixed fields (scalar values need semicolon separator after value)
    items.extend(['s:10:"requestUri"', 's:11:"/bmw/zoeken"'])
    items.extend(['s:10:"detailsUri"', 's:30:"/bmw/zoeken/resultaten/details"'])
    items.extend(['s:7:"iFramed"', 's:1:"0"'])
    items.extend(['s:4:"page"', f's:1:"{page_num}"'])

    # Serie
    serie = filters.get('serie', '')
    if serie:
        items.extend(['s:5:"serie"', f's:{len(serie)}:"{serie}"'])

    # Model (array value)
    model = filters.get('model', {})
    active_models = {k: v for k, v in model.items() if v == "1"}
    if active_models:
        model_pairs = [f's:{len(k)}:"{k}";s:1:"1"' for k in active_models.keys()]
        model_array = f'a:{len(active_models)}:{{' + ';'.join(model_pairs) + ';}'
        items.extend(['s:5:"model"', model_array])

    # Chassis (array value)
    chassis = filters.get('chassis', {})
    active_chassis = {k: v for k, v in chassis.items() if v == "1"}
    if active_chassis:
        chassis_pairs = [f's:{len(k)}:"{k}";s:1:"1"' for k in active_chassis.keys()]
        chassis_array = f'a:{len(active_chassis)}:{{' + ';'.join(chassis_pairs) + ';}'
        items.extend(['s:7:"chassis"', chassis_array])

    # Price (array value)
    price = filters.get('price', {})
    price_min = price.get('min', '')
    price_max = price.get('max', '')
    price_array = f'a:2:{{s:3:"min";s:{len(price_min)}:"{price_min}";s:3:"max";s:{len(price_max)}:"{price_max}";}}'
    items.extend(['s:5:"price"', price_array])
    items.extend(['s:12:"shadow_price"', price_array])

    # Mileage (array value)
    mileage = filters.get('mileage', {})
    mileage_min = mileage.get('min', '')
    mileage_max = mileage.get('max', '')
    mileage_array = f'a:2:{{s:3:"min";s:{len(mileage_min)}:"{mileage_min}";s:3:"max";s:{len(mileage_max)}:"{mileage_max}";}}'
    items.extend(['s:7:"mileage"', mileage_array])
    items.extend(['s:14:"shadow_mileage"', mileage_array])

    # Options (array value)
    options = filters.get('options', {})
    active_options = {k: v for k, v in options.items() if v == "1"}
    if active_options:
        option_pairs = [f'i:{k};s:1:"1"' for k in active_options.keys()]
        options_array = f'a:{len(active_options)}:{{' + ';'.join(option_pairs) + ';}'
        items.extend(['s:7:"options"', options_array])

    # isStarted flag
    items.extend(['s:9:"isStarted"', 'b:1'])

    # Build serialized string: key;value pairs where semicolon after value depends on type
    result = []
    for i in range(0, len(items), 2):
        key = items[i]
        value = items[i+1]
        result.append(key)
        result.append(';')
        result.append(value)
        # Add semicolon after value ONLY if it's NOT an array (doesn't start with 'a:')
        if not value.startswith('a:'):
            result.append(';')

    serialized = f'a:{len(items)//2}:{{' + ''.join(result) + '}'
    return serialized


def build_filter_param(filters, page_num):
    """Build the base64-encoded filter parameter for pagination"""
    php_serialized = build_php_serialized_filters(filters, page_num)
    encoded = base64.b64encode(php_serialized.encode()).decode()
    return encoded


def scrape_page(filters, page_num):
    """Scrape a single page of results"""
    filter_param = build_filter_param(filters, page_num)
    params = {"filters": filter_param}

    print(f"Fetching page {page_num}...", end=" ")

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        html = response.text

        # Find the JSON data: Action.loadVehicles($.parseJSON('{...}'), true);
        start_marker = "Action.loadVehicles($.parseJSON('"
        end_marker = "'), true);"

        start_idx = html.find(start_marker)
        if start_idx == -1:
            print("No Action.loadVehicles found")
            return []

        start_idx += len(start_marker)
        end_idx = html.find(end_marker, start_idx)

        if end_idx == -1:
            print("No end marker found")
            return []

        # Extract the JSON string (still escaped)
        json_escaped = html[start_idx:end_idx]

        # Decode the escaped JSON
        # It has backslash-escaped quotes: \" becomes "
        json_str = json_escaped.replace(r'\"', '"').replace(r"\'", "'")

        # Parse JSON
        data = json.loads(json_str)

        vehicles = data.get('vehicles', [])
        print(f"Found {len(vehicles)} vehicles")

        return vehicles

    except json.JSONDecodeError as e:
        print(f"JSON error: {e}")
        return []
    except requests.RequestException as e:
        print(f"Request error: {e}")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []


def scrape_all(dedup=True):
    """Scrape all pages"""
    print("BMW i5 Sedan Scraper")
    print("=" * 60)

    # Load filters from config
    filters = load_config()
    print(f"Loaded filters from {CONFIG_FILE}")
    print(f"  Serie: {filters.get('serie', 'N/A')}")
    print(f"  Models: {', '.join([k for k, v in filters.get('model', {}).items() if v == '1'])}")
    print(f"  Chassis: {', '.join([k for k, v in filters.get('chassis', {}).items() if v == '1'])}")
    print(f"  Price: €{filters.get('price', {}).get('min', '0')} - €{filters.get('price', {}).get('max', 'unlimited')}")
    print(f"  Mileage: {filters.get('mileage', {}).get('min', '0')} - {filters.get('mileage', {}).get('max', 'unlimited')} km")
    active_options = [k for k, v in filters.get('options', {}).items() if v == "1"]
    print(f"  Options: {len(active_options)} active")
    print("=" * 60)

    all_vehicles = []
    page = 1
    max_pages = 10

    while page <= max_pages:
        vehicles = scrape_page(filters, page)

        if not vehicles:
            if page == 1:
                print("ERROR: No vehicles found on first page")
            else:
                print(f"No more vehicles after page {page-1}")
            break

        all_vehicles.extend(vehicles)

        # Check if this was likely the last page
        if len(vehicles) < 15:  # Typically 16-18 per page
            break

        page += 1
        time.sleep(1)

    print("=" * 60)
    print(f"Total vehicles scraped: {len(all_vehicles)}")

    # Deduplicate if requested
    if dedup:
        unique_vehicles = []
        seen_ids = set()
        for v in all_vehicles:
            vid = v.get('vehicleId')
            if vid not in seen_ids:
                seen_ids.add(vid)
                unique_vehicles.append(v)

        if len(unique_vehicles) != len(all_vehicles):
            print(f"Removed {len(all_vehicles) - len(unique_vehicles)} duplicates")
            print(f"Unique vehicles: {len(unique_vehicles)}")
            all_vehicles = unique_vehicles

    return all_vehicles


def fetch_license_plate(vehicle_id):
    """Fetch license plate from vehicle detail page"""
    detail_url = f"https://occasions.bmw.nl/bmw/zoeken/resultaten/details/id/{vehicle_id}"

    try:
        response = requests.get(detail_url, timeout=15)
        html = response.text

        # Look for license plate pattern in HTML
        match = re.search(r'\b([A-Z]{1,3}-\d{1,3}-[A-Z]{1,3})\b', html)
        if match:
            return match.group(1)

        # Alternative: look for "kenteken" label
        match = re.search(r'kenteken["\s:]+([A-Z0-9-]+)', html, re.IGNORECASE)
        if match:
            return match.group(1)

    except:
        pass

    return ''


def save_csv(vehicles, filename, fetch_plates=False):
    """Save vehicles to CSV"""
    import csv

    if not vehicles:
        print("No vehicles to save")
        return

    if fetch_plates:
        print(f"\nFetching license plates...")

    # Extract fields and optionally fetch license plates
    rows = []
    for i, v in enumerate(vehicles, 1):
        vehicle_id = v.get('vehicleId', '')

        if fetch_plates:
            license_plate = fetch_license_plate(vehicle_id) if vehicle_id else ''
            if i % 10 == 0:
                print(f"  {i}/{len(vehicles)} processed")
        else:
            license_plate = ''

        # Build URL for this vehicle
        url = f"https://occasions.bmw.nl/bmw/zoeken/resultaten/details/id/{vehicle_id}" if vehicle_id else ''

        rows.append({
            'license_plate': license_plate,
            'vehicle_id': vehicle_id,
            'url': url,
            'name': v.get('name', ''),
            'model': v.get('model', ''),
            'chassis': v.get('chassis', ''),
            'price': v.get('price', ''),
            'mileage': v.get('mileage', ''),
            'year': v.get('datePartOne', '')[:4] if v.get('datePartOne') else '',
            'fuel': v.get('fuel', ''),
            'transmission': v.get('transmission', ''),
            'engine': v.get('engine', ''),
            'color': v.get('color', ''),
            'dealer': v.get('dealerName', ''),
            'city': v.get('dealerCity', ''),
        })

        if fetch_plates:
            time.sleep(0.2)  # Be nice to server

    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved to: {filename}")


def show_dashboard(vehicles):
    """Display interactive dashboard with stats and options"""
    print("\n" + "=" * 80)
    print("DASHBOARD")
    print("=" * 80)

    # Basic stats
    print(f"\nTotal vehicles: {len(vehicles)}")

    if not vehicles:
        return

    # Price stats
    prices = [int(v['price']) for v in vehicles if v.get('price')]
    if prices:
        avg_price = sum(prices) / len(prices)
        print(f"Price range: €{min(prices):,} - €{max(prices):,}")
        print(f"Average price: €{avg_price:,.0f}")

    # Mileage stats
    mileages = [int(v['mileage']) for v in vehicles if v.get('mileage')]
    if mileages:
        avg_mileage = sum(mileages) / len(mileages)
        print(f"Mileage range: {min(mileages):,} - {max(mileages):,} km")
        print(f"Average mileage: {avg_mileage:,.0f} km")

    # Year distribution
    years = [v.get('datePartOne', '')[:4] for v in vehicles if v.get('datePartOne')]
    if years:
        from collections import Counter
        year_counts = Counter(years)
        print(f"\nYear distribution:")
        for year, count in sorted(year_counts.items(), reverse=True):
            print(f"   {year}: {count} vehicles")

    # Color distribution
    colors = [v.get('color', 'Unknown') for v in vehicles]
    color_counts = Counter(colors)
    print(f"\nTop colors:")
    for color, count in color_counts.most_common(3):
        print(f"   {color}: {count} vehicles")

    print("=" * 80)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='BMW i5 Scraper')
    parser.add_argument('--no-check', action='store_true', help='Skip interactive check, proceed directly')
    parser.add_argument('--auto-rdw', action='store_true', help='Automatically run RDW enrichment after scraping')
    parser.add_argument('--auto-export', action='store_true', help='Automatically export to Excel after RDW enrichment')
    args = parser.parse_args()

    choice = None  # Initialize choice variable

    # Scrape all pages
    vehicles = scrape_all()

    if not vehicles:
        print("\nNo vehicles found. Check the URL or try again.")
        return 1

    # Save files
    date_str = datetime.now().strftime('%Y-%m-%d')

    # Save raw JSON
    json_file = f"vehicles_raw_{date_str}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(vehicles, f, indent=2, ensure_ascii=False)
    print(f"\nRaw JSON: {json_file}")

    # Save CSV
    csv_file = f"vehicles_{date_str}.csv"
    save_csv(vehicles, csv_file)

    # Show dashboard
    show_dashboard(vehicles)

    # Interactive check (unless --no-check or --auto-rdw)
    if not args.no_check and not args.auto_rdw:
        print("\nProceed with RDW enrichment?")
        print("  [Y] Yes, fetch license plates and run RDW")
        print("  [N] No, stop here")
        choice = input("\nChoice: ").strip().upper()

        if choice != 'Y':
            print("\nStopped. CSV saved without license plates.")
            print("To continue: python enrich_rdw.py vehicles_YYYY-MM-DD.csv")
            return 0
        else:
            # Fetch license plates now
            print("\nFetching license plates...")
            for i, v in enumerate(vehicles, 1):
                vehicle_id = v.get('vehicleId', '')
                if vehicle_id:
                    v['license_plate'] = fetch_license_plate(vehicle_id)
                    if i % 10 == 0:
                        print(f"  {i}/{len(vehicles)} processed")
                    time.sleep(0.2)

            # Re-save CSV with license plates
            import csv as csv_module
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv_module.DictWriter(f, fieldnames=['license_plate', 'vehicle_id', 'url', 'name', 'model', 'chassis', 'price', 'mileage', 'year', 'fuel', 'transmission', 'engine', 'color', 'dealer', 'city'])
                writer.writeheader()
                for v in vehicles:
                    vehicle_id = v.get('vehicleId', '')
                    writer.writerow({
                        'license_plate': v.get('license_plate', ''),
                        'vehicle_id': vehicle_id,
                        'url': f"https://occasions.bmw.nl/bmw/zoeken/resultaten/details/id/{vehicle_id}" if vehicle_id else '',
                        'name': v.get('name', ''),
                        'model': v.get('model', ''),
                        'chassis': v.get('chassis', ''),
                        'price': v.get('price', ''),
                        'mileage': v.get('mileage', ''),
                        'year': v.get('datePartOne', '')[:4] if v.get('datePartOne') else '',
                        'fuel': v.get('fuel', ''),
                        'transmission': v.get('transmission', ''),
                        'engine': v.get('engine', ''),
                        'color': v.get('color', ''),
                        'dealer': v.get('dealerName', ''),
                        'city': v.get('dealerCity', ''),
                    })
            print(f"Updated {csv_file} with license plates")

    # Fetch plates for auto modes
    if args.auto_rdw or args.no_check:
        print("\nFetching license plates...")
        for i, v in enumerate(vehicles, 1):
            vehicle_id = v.get('vehicleId', '')
            if vehicle_id:
                v['license_plate'] = fetch_license_plate(vehicle_id)
                if i % 10 == 0:
                    print(f"  {i}/{len(vehicles)} processed")
                time.sleep(0.2)

        # Re-save CSV with license plates
        import csv as csv_module
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv_module.DictWriter(f, fieldnames=['license_plate', 'vehicle_id', 'url', 'name', 'model', 'chassis', 'price', 'mileage', 'year', 'fuel', 'transmission', 'engine', 'color', 'dealer', 'city'])
            writer.writeheader()
            for v in vehicles:
                vehicle_id = v.get('vehicleId', '')
                writer.writerow({
                    'license_plate': v.get('license_plate', ''),
                    'vehicle_id': vehicle_id,
                    'url': f"https://occasions.bmw.nl/bmw/zoeken/resultaten/details/id/{vehicle_id}" if vehicle_id else '',
                    'name': v.get('name', ''),
                    'model': v.get('model', ''),
                    'chassis': v.get('chassis', ''),
                    'price': v.get('price', ''),
                    'mileage': v.get('mileage', ''),
                    'year': v.get('datePartOne', '')[:4] if v.get('datePartOne') else '',
                    'fuel': v.get('fuel', ''),
                    'transmission': v.get('transmission', ''),
                    'engine': v.get('engine', ''),
                    'color': v.get('color', ''),
                    'dealer': v.get('dealerName', ''),
                    'city': v.get('dealerCity', ''),
                })
        print(f"Updated {csv_file} with license plates")

    # Run RDW enrichment if requested
    if args.auto_rdw or (choice and choice == 'Y'):
        print("\n" + "=" * 80)
        print("Running RDW enrichment...")
        print("=" * 80)
        import subprocess
        result = subprocess.run([sys.executable, 'enrich_rdw.py', csv_file], capture_output=False)

        if result.returncode != 0:
            print("\nRDW enrichment failed")
            return 1

        # Find enriched file
        from pathlib import Path
        enriched_files = list(Path('.').glob('vehicles_enriched_*.csv'))
        if not enriched_files:
            print("\nNo enriched file found")
            return 1

        enriched_csv = sorted(enriched_files)[-1]

        # Show enriched stats
        import csv as csv_module
        with open(enriched_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv_module.DictReader(f)
            enriched = list(reader)

        # Sort by discount descending
        sorted_vehicles = sorted(enriched, key=lambda x: float(x.get('discount_percent', '0') or '0'), reverse=True)

        # All vehicles detailed table
        print("\n" + "=" * 120)
        print("ALL VEHICLES (Sorted by Discount)")
        print("=" * 120)
        max_dealer_len = min(20, max((len(v.get('dealer', '')) for v in sorted_vehicles), default=10))
        print(f"{'Plate':<12} {'First Reg':<12} {'Mileage':<10} {'Color':<15} {'Dealer':<{max_dealer_len}} {'Cat.Price':<12} {'Price':<12} {'Discount':<10}")
        print("-" * 120)
        for v in sorted_vehicles:
            plate = v.get('license_plate', '')[:11]
            first_reg = v.get('first_registration', '')[:11]
            mileage = v.get('mileage', '')
            if mileage:
                mileage = f"{int(mileage):,}"[:9]
            color = v.get('color', '')[:14]
            dealer = v.get('dealer', '')[:max_dealer_len-1]
            cat_price = v.get('catalogue_price', '')
            if cat_price:
                cat_price = f"€{cat_price}"[:11]
            price = f"€{v.get('price', '')}"[:11]
            discount = v.get('discount_percent', '')
            if discount:
                discount = f"{discount}%"
            print(f"{plate:<12} {first_reg:<12} {mileage:<10} {color:<15} {dealer:<{max_dealer_len}} {cat_price:<12} {price:<12} {discount:<10}")
        print("=" * 120)

        # Export to Excel if requested
        if args.auto_export:
            # Display separator line and status message for Excel export process
            # The separator line (80 equals signs) provides visual separation in console output
            print("\n" + "=" * 80)
            print("Exporting to Excel...")
            print("=" * 80)
            result = subprocess.run([sys.executable, 'convert_to_xlsx.py'], capture_output=False)

            if result.returncode != 0:
                print("\nExcel export failed")
                return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
