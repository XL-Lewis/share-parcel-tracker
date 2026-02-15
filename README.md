# Tax Tracker

Australian CGT (Capital Gains Tax) tracker for share portfolios. Import trades from CSV, match sell transactions against buy parcels using FIFO/LIFO/manual strategies, and calculate capital gains with CGT discount eligibility.

## Features

- **CSV Import** -- Import trades from SelfWealth exports or generic CSV files with column mapping
- **Parcel Tracking** -- Automatic parcel creation from buy transactions with cost base calculation
- **Matching Engine** -- Match sells to buy parcels using FIFO, LIFO, or manual selection
- **CGT Calculation** -- Australian tax rules: 50% discount for holdings >365 days, AUD conversion for international shares
- **Dashboard** -- Portfolio overview with holdings, cost base, realised gains, and unmatched sells
- **HTMX UI** -- Interactive matching workflow with live preview before committing

## Requirements

- Python >= 3.14
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
# Clone the repo
git clone <repo-url> && cd tax-tracker

# Install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Create a superuser (optional, for admin access)
uv run python manage.py createsuperuser
```

## Running the Server

```bash
uv run python manage.py runserver
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

## Pages

| URL | Description |
|-----|-------------|
| `/` | Dashboard -- portfolio overview and stats |
| `/transactions/` | Transaction list with filtering |
| `/transactions/<id>/` | Transaction detail with linked parcel/matches |
| `/parcels/` | Parcel list with security and status filters |
| `/parcels/<id>/` | Parcel detail with match history |
| `/matching/` | Match unmatched sell transactions to parcels |
| `/import/upload/` | Import trades from CSV |
| `/admin/` | Django admin interface |

## Running Tests

```bash
uv run python manage.py test tracker
```

For verbose output:

```bash
uv run python manage.py test tracker --verbosity=2
```

## Stack

- **Backend**: Django 6.x, Python 3.14, SQLite
- **Frontend**: HTMX, Alpine.js, Tailwind CSS (all via CDN, no build step)
- **Packages**: django-htmx, whitenoise

## Project Structure

```
tax-tracker/
├── config/                    # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── tracker/                   # Main app
│   ├── models/                # Models as a package
│   │   ├── security.py        # Security (ticker, exchange, currency)
│   │   ├── transaction.py     # Transaction (buy/sell)
│   │   ├── parcel.py          # Parcel + ParcelMatch
│   │   └── import_record.py   # CSV import metadata
│   ├── services/
│   │   ├── csv_import.py      # CSV parsing + import pipeline
│   │   ├── cgt.py             # CGT calculation + FY summary
│   │   └── matching.py        # FIFO/LIFO/manual matching engine
│   ├── views/
│   │   ├── dashboard.py       # Portfolio overview
│   │   ├── transactions.py    # Transaction list/detail + CSV import flow
│   │   ├── parcels.py         # Parcel list/detail
│   │   └── matching.py        # HTMX matching workflow
│   ├── templates/tracker/     # HTML templates
│   └── tests/                 # Test suite
├── manage.py
└── pyproject.toml
```
