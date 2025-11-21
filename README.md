# BMW i5 Scraper

Web-based BMW i5 vehicle scraper with interactive dashboard.

## Features

- Scrapes BMW i5 vehicles from occasions.bmw.nl
- Enriches data with RDW registration information
- Calculates discounts from catalogue prices
- Interactive web dashboard with vehicle cards
- Christmas theme toggle
- Sortable by discount percentage

## Installation

```bash
pip install -r requirements.txt
```

## Usage

1. Configure filters in `config.json`
2. Start web server:
   ```bash
   python web_server.py
   ```
3. Open http://localhost:5000
4. Click "Run Scraper" to fetch latest data

## Files

- `i5-scraper.py` - Main scraper script
- `web_server.py` - Flask web server
- `index.html` - Dashboard interface
- `enrich_rdw.py` - RDW data enrichment
- `convert_to_xlsx.py` - Excel export
- `config.json` - Search filters

## Dashboard

Beautiful responsive interface featuring:
- Vehicle cards with images
- Price comparison (catalogue vs selling)
- Direct links to listings
- Live stats (total vehicles, best discount)
- Christmas theme with animated snowflakes
