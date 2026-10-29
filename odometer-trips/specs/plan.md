# Odometer Trip Log: project plan (approved 2026-10-29)

Copy of the approved plan, so Claude Code can read it. Source of record: the owner's Docs artifact.

## Project description

A single-user web app that records each trip as a start and end odometer reading and reports distance, fuel use and service timing. Version 1 is one HTML page for a tablet browser, with data kept on the device and exported to CSV. It is also the first live test of the github-loop workflow.

Objectives:
1. Record a trip in under 30 seconds on a tablet (target, timed in the Phase 1 browser check).
2. Reject an end reading below the start reading, and a start reading below the vehicle's last end reading.
3. Show monthly distance, fuel litres, fuel cost and km per litre for each vehicle.
4. Show the kilometres remaining to each service due.
5. Export every table to CSV, and keep all data after a page reload.

| Area | In version 1 | Not in version 1 |
| --- | --- | --- |
| Records | Vehicles, trips with purpose and destination, fuel refills, service history | Receipt photos, GPS tracks |
| Reports | Monthly report per vehicle, CSV export | Charts, reimbursement forms |
| Users | One owner on one device | Other users, sign-in, approvals |
| Storage | Browser storage on the device | Google Sheets sync (Phase 3), full-stack database |

## Modules and workflows

| ID | Module | Key records | Output |
| --- | --- | --- | --- |
| M1 | Vehicles | Name, plate, fuel type, starting odometer | Vehicle list |
| M2 | Trips | Date, start and end odometer, purpose, destination | Trip list with distance per trip |
| M3 | Fuel | Date, odometer, litres, cost, full tank | Km per litre, fuel cost per month |
| M4 | Service | Service name, interval in km, completed services | Km remaining to the next service |
| M5 | Reports and export | All of the above | Monthly report, CSV files |

Trip status: Open (vehicle and date chosen; start reading defaults to the vehicle's last end reading) → Closed (end reading entered, rejected if below start) → Voided (never deleted; change logged).
Service status: OK → Due soon (within 500 km of the due reading) → Overdue (odometer passed the due reading) → Done (logging the service restarts the interval from that reading).

## Architecture

Plain HTML, CSS and JavaScript in one page. Four layers:

| Layer | Version 1 | After migration | Must stay the same |
| --- | --- | --- | --- |
| Screens | HTML and CSS, tablet first | Same screens | Screens call only the API client |
| API client (`api.js`) | Transport `local` | Transport `appsscript`, later `rest` | Function names and return shapes |
| Services | Validation, distance, km per litre, service due | Same code | Business rules live only here |
| Repository | Browser storage | Google Sheets through Apps Script, later PostgreSQL | Only this layer reads or writes data |

Rules: one table per record type, snake_case columns, prefixed ID as primary key; audit columns on every table (created_at, created_by, updated_at, updated_by, is_active, row_version); odometer in whole km, litres with two decimals, cost in PHP; a `mock` transport reads fixtures from `tests/fixtures/`. Browser storage is about 5 MB and can be cleared, so every report offers a CSV export.

## Data model

Every table also carries the six audit columns.

| Table | ID prefix | Key columns | Links to |
| --- | --- | --- | --- |
| vehicles | VEH | name, plate, fuel_type, start_odometer_km | none |
| trips | TRP | vehicle_id, trip_date, start_km, end_km, purpose_id, destination, status | vehicles, lookups |
| fuel_logs | FUE | vehicle_id, fill_date, odometer_km, litres, total_cost, is_full_tank | vehicles |
| service_rules | SVR | vehicle_id, service_name, interval_km | vehicles |
| service_logs | SVC | rule_id, done_date, odometer_km, cost | service_rules |
| lookups | LKP | group_name, value (for example trip purpose) | none |
| audit_log | AUD | table_name, record_id, action, changed_at | every table |

## Roadmap (weeks are estimates)

| Phase | Weeks | Content | Gate |
| --- | --- | --- | --- |
| 0 Loop setup | 1 | Repo, labels, skill, scheduled task | A test issue gets a turn-2 reply and a `to-chat` label |
| 1 Core trips | 2-3 | Vehicles, trips, CSV with validation | Tests pass; browser checks at 1280, 768, 375 px; PR review clean |
| 2 Fuel, service | 4-5 | Fuel log, service due, monthly report | Same checks; service due matches a hand calculation |
| 3 Sheets sync | 6-7 | Apps Script sheet, import, switch over | Data imported; local copy set to read-only |

## Source control

Repository `lheiiyy/test` (public), folder `odometer-trips/`. `main` is the live copy; all work lands on `claude/` branches and merges through a pull request that the owner reviews. Proposed deploy path: GitHub Pages. No secrets in version 1; never commit real trip data, and use dummy values in tests.

## Migration plan (Phase 3)

1. Create a Google Sheet with one tab per table, and a separate Apps Script project.
2. Write the Apps Script repository with the same function names as the local one.
3. Add the `appsscript` transport to `api.js` and run the existing tests against the mock transport.
4. Export the device's CSV files, import them into the sheet once, and compare row counts per table.
5. Switch the transport setting and run one smoke test on the deployed app; the owner signs in.
6. Keep the local copy read-only for one month, then retire it.

## Assumptions approved with the plan

Kilometres, litres and PHP. A trip may stay open (start now, end later). Service reminder margin is 500 km. Hosting by GitHub Pages is proposed, not yet enabled.
