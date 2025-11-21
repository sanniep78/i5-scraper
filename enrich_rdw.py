#!/usr/bin/env python3
"""
RDW Enrichment Script
Takes scraped BMW vehicles and adds RDW fiscal catalogue prices
"""

import csv
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("Missing dependency. Install with:")
    print("  pip install requests")
    sys.exit(1)

RDW_API = "https://opendata.rdw.nl/resource/m9d7-ebf2.json"


def query_rdw(license_plate):
    """Query RDW API for vehicle fiscal data"""
    if not license_plate:
        return None

    # Remove dashes for API
    kenteken = license_plate.replace('-', '').upper()

    try:
        response = requests.get(
            RDW_API,
            params={'kenteken': kenteken},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]

    except:
        pass

    return None


def enrich_vehicles(input_csv):
    """Enrich vehicles with RDW data"""
    print(f"Reading {input_csv}...")

    # Read input CSV
    with open(input_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        vehicles = list(reader)

    print(f"Found {len(vehicles)} vehicles")
    print("\nQuerying RDW API...")

    enriched = []
    for i, vehicle in enumerate(vehicles, 1):
        plate = vehicle.get('license_plate', '')

        print(f"[{i}/{len(vehicles)}] {plate}...", end=' ')

        rdw = query_rdw(plate)

        if rdw:
            catalogue_price = rdw.get('catalogusprijs', '')
            listing_price = vehicle.get('price', '')

            # Calculate discount
            discount_pct = ''
            if catalogue_price and listing_price:
                try:
                    cat_price_num = int(catalogue_price)
                    list_price_num = int(listing_price)
                    discount_pct = round(((cat_price_num - list_price_num) / cat_price_num) * 100, 1)
                except:
                    pass

            enriched.append({
                **vehicle,
                'catalogue_price': catalogue_price,
                'discount_percent': discount_pct,
                'rdw_model': rdw.get('handelsbenaming', ''),
                'rdw_make': rdw.get('merk', ''),
                'first_registration': rdw.get('datum_eerste_toelating', ''),
            })

            print(f"OK (€{catalogue_price}, {discount_pct}% off)")
        else:
            enriched.append({
                **vehicle,
                'catalogue_price': '',
                'discount_percent': '',
                'rdw_model': '',
                'rdw_make': '',
                'first_registration': '',
            })
            print("No RDW data")

        time.sleep(0.1)  # Rate limiting

    return enriched


def save_enriched(vehicles, output_csv):
    """Save enriched data to CSV"""
    if not vehicles:
        print("No data to save")
        return

    with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=vehicles[0].keys())
        writer.writeheader()
        writer.writerows(vehicles)

    print(f"\nSaved to: {output_csv}")


def print_summary(vehicles):
    """Print summary with best deals"""
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    # Filter vehicles with discount data
    with_discounts = [v for v in vehicles if v.get('discount_percent')]

    print(f"Total vehicles: {len(vehicles)}")
    print(f"With RDW data: {len(with_discounts)}")

    if with_discounts:
        # Sort by discount
        sorted_deals = sorted(with_discounts, key=lambda x: float(x['discount_percent']), reverse=True)

        print(f"\nTop 5 Deals:")
        print("-"*80)
        print(f"{'Plate':<12} {'Name':<30} {'Price':<10} {'Cat.Price':<10} {'Discount':<10}")
        print("-"*80)

        for deal in sorted_deals[:5]:
            plate = deal.get('license_plate', '')
            name = deal.get('name', '')[:28]
            price = f"€{deal.get('price', '')}".ljust(10)
            cat_price = f"€{deal.get('catalogue_price', '')}".ljust(10)
            discount = f"{deal.get('discount_percent', '')}%"

            print(f"{plate:<12} {name:<30} {price:<10} {cat_price:<10} {discount:<10}")

    print("="*80)


def main():
    if len(sys.argv) < 2:
        print("Usage: python enrich_rdw.py <input_csv>")
        print("Example: python enrich_rdw.py vehicles_2025-11-18.csv")
        return 1

    input_csv = sys.argv[1]

    # Generate output filename
    date_str = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    output_csv = f"vehicles_enriched_{date_str}.csv"

    # Enrich
    enriched = enrich_vehicles(input_csv)

    # Save
    save_enriched(enriched, output_csv)

    # Summary
    print_summary(enriched)

    return 0


if __name__ == '__main__':
    sys.exit(main())
