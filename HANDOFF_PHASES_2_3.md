CONTEXT_SUMMARY
project: tax-tracker
cwd: /home/lewishyman/git/tax-tracker
branch: main

CONVERSATION_STATE
pending_tasks: [Phase 2: Matching Engine + Core UI, Phase 3: Reports + Forecasting]

KEY_DECISIONS
- Django 5.x + Python 3.14 + SQLite: simple stack, no external DB
- HTMX for server interactions, Alpine.js for local UI state, Tailwind CDN: no JS build step
- Python Decimal throughout: no floats for money, all DecimalField(max_digits=18, decimal_places=6)
- Models as package: tracker/models/ with __init__.py re-exporting all models
- ParcelMatch stores computed CGT fields at match time (not derived on read)
- Matching engine returns unsaved objects for preview before persistence
- Australian FY: Jul 1 - Jun 30, CGT discount >365 days (individuals), 50% discount on positive gains only
- Cost base includes brokerage, AUD conversion via exchange_rate on Transaction
- Duplicate detection via unique constraint on (trade_date, security, transaction_type, quantity, unit_price)

TECHNICAL_CONTEXT
stack: [Django 5.x, Python 3.14, SQLite, HTMX, Alpine.js, Tailwind CSS CDN, django-htmx, whitenoise]
patterns: [service-layer (services/), model-package, HTMX-partial-responses, preview-before-commit]
constraints: [no floats for money, no JS build step, CDN only for frontend libs]

DATA_MODEL
Security: ticker(unique), name, exchange(ASX/NYSE/NASDAQ), currency(AUD/USD), asset_type(SHARE/ETF)
Transaction: FK security, FK import_record(nullable), trade_date, transaction_type(BUY/SELL), quantity, unit_price, brokerage, total_value, currency, exchange_rate(default=1), raw_data(JSON)
Parcel: OneToOne transaction, FK security, acquisition_date, original_quantity, remaining_quantity, cost_per_unit_aud, total_cost_base_aud, is_fully_matched
ParcelMatch: FK parcel, FK sell_transaction, matched_quantity, cost_base_aud, proceeds_aud, capital_gain_loss, holding_period_days, cgt_discount_eligible, discount_amount, net_capital_gain
ImportRecord: filename, imported_at(auto), source_type(SELFWEALTH/GENERIC), row_count, column_mapping(JSON)

PHASE_1_COMPLETED (expected state when this handoff is used)
- Django project scaffolded at config/, tracker app created
- All 5 models defined in tracker/models/ package, migrations run
- Admin registered with list_display, filters, ParcelMatch inlines
- CSV import service: SelfWealth + generic adapters, preview + confirm pipeline
- CSV import views/templates: upload -> mapping -> preview -> confirm
- base.html with Tailwind CDN + HTMX + Alpine.js
- Tests for models + CSV import passing

PHASE_2_SPEC: Matching Engine + Core UI

Services to build:

tracker/services/matching.py:
- def match(sell_transaction, strategy="fifo", parcels=None, quantities=None) -> list[ParcelMatch] (unsaved)
- FIFO: Parcel.objects.filter(security=sell.security, remaining_quantity__gt=0).order_by('acquisition_date')
- LIFO: same query .order_by('-acquisition_date')
- Manual: iterate user-provided (parcel, qty) pairs
- Validation: total matched qty == sell qty, per-parcel qty <= remaining
- def confirm_matches(matches): save ParcelMatch records, decrement parcel.remaining_quantity, set is_fully_matched, all in transaction.atomic()

tracker/services/cgt.py:
- def calculate_cgt(parcel, sell_transaction, matched_quantity) -> dict with cost_base_aud, proceeds_aud, capital_gain_loss, holding_period_days, cgt_discount_eligible, discount_amount, net_capital_gain
- Called by matching engine when creating ParcelMatch objects
- Holding period: (sell.trade_date - parcel.acquisition_date).days
- Discount: 50% if holding_period_days > 365 AND gain > 0
- AUD conversion: unit_price * quantity * exchange_rate for cost and proceeds
- def fy_summary(financial_year) -> aggregated gains/losses/discounts for FY (Jul 1 - Jun 30)

Views to build:

tracker/views/dashboard.py - DashboardView:
- Holdings per security (sum remaining_quantity across parcels)
- Unrealised gain estimate
- Unmatched sell transactions count

tracker/views/transactions.py (extend Phase 1):
- Filterable list (security, type, date range)
- Detail view: raw data, linked parcel (BUY), linked matches (SELL)
- Templates: transactions/list.html, detail.html

tracker/views/parcels.py:
- List: filterable by security, matched/unmatched
- Detail: acquisition info, remaining qty, all matches
- Templates: parcels/list.html, detail.html

tracker/views/matching.py (key HTMX page):
- List unmatched sells
- Click sell -> HTMX GET loads available parcels partial for that security
- "Auto FIFO"/"Auto LIFO" buttons -> HTMX POST runs engine, returns preview partial
- Manual mode: Alpine.js quantity inputs per parcel, hx-post for CGT preview
- "Confirm" button -> HTMX POST persists matches, returns updated state
- Templates: matching/match_sell.html, partials/parcel_list.html, partials/match_preview.html, partials/match_confirmed.html

Phase 2 tests:
- tracker/tests/test_matching.py: FIFO ordering, LIFO ordering, manual matching, partial matching (buy 100, sell 60 then 40), over-match rejection, remaining_quantity updates, is_fully_matched flag
- tracker/tests/test_cgt.py: discount eligibility (>365d), short-term (no discount), losses (no discount), AUD conversion, FY aggregation boundaries (Jun 30 vs Jul 1)
- tracker/tests/test_views.py: view smoke tests, HTMX partial responses return correct fragments

PHASE_3_SPEC: Reports + Forecasting

tracker/views/reports.py:
- FY selector dropdown (years with existing matches)
- Per-FY summary: total gains, total losses, total discounts, net position
- Per-security breakdown within each FY
- Template: reports/cgt_summary.html

tracker/services/forecasting.py:
- def forecast(security, quantity, sell_price, sell_date=today) -> dict with fifo/lifo/optimal results
- Optimal strategy: sort parcels by cost_per_unit_aud DESC (highest cost first = minimize gain)
- Each result: parcels consumed, per-parcel CGT breakdown, total gain/loss/discount
- Preview mode only, no DB writes

tracker/views/reports.py (extend):
- Forecast form: security select + quantity + price inputs
- HTMX submit -> side-by-side comparison partial (FIFO vs LIFO vs Optimal)
- Templates: reports/forecast.html, partials/forecast_results.html

Dashboard polish:
- Total cost base, total holdings count, top holdings
- Recent activity (latest imports, latest matches)
- Quick-links to unmatched sells

Phase 3 tests:
- tracker/tests/test_forecasting.py: mixed discount/non-discount parcels, optimal ordering, no parcels edge case, insufficient qty
- tracker/tests/test_reports.py: FY boundary logic, multi-FY aggregation, empty FY

E2E_TESTS (span all phases):
- tracker/tests/test_e2e.py:
  1. Import CSV -> verify txns + parcels -> match sell FIFO -> verify ParcelMatch + CGT + remaining_qty
  2. Partial matching: buy 100, sell 60 (40 remaining), sell 40 (fully matched)
  3. Multi-security: mixed import, independent matching, no cross-contamination
  4. International shares: USD txns with exchange_rate, verify AUD cost base/proceeds
  5. FY report accuracy: matches spanning FYs, verify aggregation boundaries
  6. Forecast consistency: forecast then execute same match, verify forecast == actual
  7. Duplicate import rejection: same CSV twice, no duplicates
  8. Edge cases: zero brokerage, single-unit parcels, same-day buy+sell, exact 365-day boundary

VALIDATION_CHECKLIST
- All money fields use Decimal, no floats in codebase
- CGT discount: 365 days = no discount, 366 = discount
- exchange_rate defaults to 1.0 for AUD
- remaining_quantity never goes negative
- All DB writes in matching/import wrapped in transaction.atomic()

CONTEXT_REFERENCES
relevant_docs: [config/settings.py, tracker/models/__init__.py, tracker/services/__init__.py]
dependencies: [django, django-htmx, whitenoise]
