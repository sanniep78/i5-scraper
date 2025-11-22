#!/usr/bin/env python3
"""
Flask web server for BMW i5 scraper
"""

import csv
import json
import subprocess
import sys
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from rate_limiter import rate_limit, simple_auth

app = Flask(__name__, static_folder='.')
CORS(app)


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/scrape', methods=['POST'])
@rate_limit(max_requests=3, window_seconds=3600)  # 3 requests per hour
@simple_auth  # Requires password if SCRAPER_PASSWORD env var is set
def scrape():
    """Execute the i5-scraper script"""
    try:
        result = subprocess.run(
            [sys.executable, 'i5-scraper.py', '--no-check', '--auto-rdw'],
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            return jsonify({
                'success': False,
                'error': result.stderr or result.stdout
            }), 500

        return jsonify({
            'success': True,
            'output': result.stdout
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Scraper timeout after 10 minutes'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/vehicles')
def get_vehicles():
    """Get latest enriched vehicle data merged with raw data"""
    try:
        # Get sort parameter (default: discount)
        sort_by = request.args.get('sort', 'discount')

        # Find most recent files
        enriched_files = list(Path('.').glob('vehicles_enriched_*.csv'))
        raw_files = list(Path('.').glob('vehicles_raw_*.json'))

        if not enriched_files:
            return jsonify({
                'success': False,
                'error': 'No enriched data found. Run scraper first.'
            }), 404

        latest_enriched = sorted(enriched_files)[-1]
        latest_raw = sorted(raw_files)[-1] if raw_files else None

        # Read enriched CSV
        enriched_data = {}
        with open(latest_enriched, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                vehicle_id = row.get('vehicle_id', '')
                enriched_data[vehicle_id] = row

        # Read raw JSON for images
        raw_data = {}
        if latest_raw:
            with open(latest_raw, 'r', encoding='utf-8') as f:
                raw_vehicles = json.load(f)
                for v in raw_vehicles:
                    vehicle_id = v.get('vehicleId', '')
                    raw_data[vehicle_id] = v

        # Merge data
        vehicles = []
        for vehicle_id, enriched in enriched_data.items():
            vehicle = enriched.copy()

            # Add image from raw data
            if vehicle_id in raw_data:
                thumbnails = raw_data[vehicle_id].get('thumbnails', [])
                vehicle['image'] = thumbnails[0] if thumbnails else ''
            else:
                vehicle['image'] = ''

            vehicles.append(vehicle)

        # Sort based on parameter
        if sort_by == 'newest':
            # Sort by first_seen descending (newest first)
            vehicles.sort(
                key=lambda x: x.get('first_seen', ''),
                reverse=True
            )
        elif sort_by == 'oldest':
            # Sort by first_seen ascending (oldest first)
            vehicles.sort(
                key=lambda x: x.get('first_seen', '')
            )
        elif sort_by == 'price_low':
            vehicles.sort(
                key=lambda x: int(x.get('price', '0') or '0')
            )
        elif sort_by == 'price_high':
            vehicles.sort(
                key=lambda x: int(x.get('price', '0') or '0'),
                reverse=True
            )
        else:  # Default: discount
            vehicles.sort(
                key=lambda x: float(x.get('discount_percent', '0') or '0'),
                reverse=True
            )

        return jsonify({
            'success': True,
            'vehicles': vehicles,
            'file': str(latest_enriched),
            'count': len(vehicles),
            'sort': sort_by
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("Starting BMW i5 Scraper Web Interface...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(debug=False, host='0.0.0.0', port=port)
