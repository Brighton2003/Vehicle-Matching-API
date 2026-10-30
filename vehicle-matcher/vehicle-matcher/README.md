# Vehicle Matching API

A REST API that takes a customer's vehicle requirements and returns the best-matching vehicles from a dealership inventory, ranked by a transparent, explainable score.

> "I'm looking for an automatic Toyota SUV under R250,000 with less than 100,000 km."  
> → `POST /api/v1/vehicles/match` → ranked vehicles, each with a score and the reasons behind it.

Built with **Python 3.12+, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite and Pytest**, with Docker support.

## Contents

1. [Quick start](#quick-start)
2. [Configuration](#configuration-environment-variables)
3. [Database setup](#database-setup)
4. [API reference](#api-reference)
5. [Error handling](#error-handling)
6. [Matching algorithm](#matching-algorithm)
7. [Running the tests](#running-the-tests)
8. [Docker](#docker)
9. [Technical explanation](#technical-explanation) (architecture, database design, technology choices, trade-offs, future improvements)
10. [Answer to the final question: scaling](#final-question-100000-vehicles-and-50000-searches-per-day)
11. [Submission details](#submission-details)

## Quick start

```bash
git clone <repository-url> vehicle-matcher
cd vehicle-matcher

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI (OpenAPI schema at `/openapi.json`, ReDoc at `/redoc`).

On first start the app creates the tables and seeds the sample inventory automatically if the database is empty, so there is nothing else to run.

Try it:

```bash
curl -X POST http://localhost:8000/api/v1/vehicles/match \
  -H "Content-Type: application/json" \
  -d '{"budget_max": 250000, "brand": "Toyota", "transmission": "automatic", "body_type": "SUV", "max_mileage": 100000}'
```

## Configuration (environment variables)

All settings are optional. They are read from the environment or a `.env` file, and are prefixed with `VM_`.

| Variable | Default | Description |
|---|---|---|
| `VM_DATABASE_URL` | `sqlite:///./vehicles.db` | SQLAlchemy database URL. Any SQLAlchemy-supported database works, e.g. `postgresql+psycopg://user:pw@host/db` (install the matching driver). |
| `VM_AUTO_SEED` | `true` | Seed sample vehicles on startup when the table is empty. Set to `false` in production. |
| `VM_DEFAULT_PAGE_LIMIT` | `10` | Default `limit` for `GET /api/v1/vehicles`. |
| `VM_MAX_PAGE_LIMIT` | `100` | Maximum allowed `limit` for `GET /api/v1/vehicles`. |

## Database setup

The schema is created automatically on startup (`Base.metadata.create_all`). To populate it manually:

```bash
python -m scripts.seed            # seed only if the table is empty (idempotent)
python -m scripts.seed --reset    # wipe the vehicles table and re-seed
```

The seed script inserts **44 vehicles** (43 available, 1 unavailable) across 14 makes, with a mix of body types, transmissions, fuel types, prices (R109,900 – R599,900) and mileages. The data lives in `app/seed_data.py`.

## API reference

Interactive docs: `/docs`. Summary below.

### `POST /api/v1/vehicles/match`

Finds and ranks vehicles. **All criteria are optional, but at least one is required** (an empty `{}` is rejected).

| Field | Type | Rules |
|---|---|---|
| `budget_max` | number | `> 0` |
| `brand` | string | non-empty; case-insensitive; aliases and typos are resolved (`vw`, `merc`, `Toyata`) |
| `transmission` | string | `Automatic` or `Manual`; case-insensitive; `Auto`, `CVT`, `Stick`… accepted |
| `body_type` | string | `Hatchback`, `Sedan`, `SUV`, `Bakkie`, `Coupe`, `Minivan`; aliases such as `hatch`, `pickup` accepted |
| `fuel_type` | string | `Petrol`, `Diesel`, `Hybrid`, `Electric` (`EV` accepted) |
| `max_mileage` | integer | `>= 0` (km) |
| `min_year` | integer | 1980 – next calendar year |
| `query` | string | *(bonus)* free-text, e.g. `"I need an automatic Toyota SUV under R250k"`. Explicit fields override anything parsed from it. |
| `limit` | integer | 1–50, default 10. Caps the number of returned matches (`total_matches` is unaffected). |
| `min_score` | integer | 0–100, default 50. Vehicles scoring below this are not returned. |

**Request**

```json
{
  "budget_max": 250000,
  "brand": "Toyota",
  "transmission": "automatic",
  "body_type": "SUV",
  "max_mileage": 100000
}
```

**Response `200 OK`** (trimmed to two matches)

```json
{
  "total_matches": 19,
  "matches": [
    {
      "vehicle_id": 1,
      "make": "Toyota",
      "model": "Urban Cruiser",
      "variant": "1.5 XR",
      "year": 2021,
      "price": 229900,
      "mileage": 48000,
      "fuel_type": "Petrol",
      "transmission": "Automatic",
      "body_type": "SUV",
      "colour": "White",
      "match_score": 100,
      "reasons": [
        "Brand matches: Toyota",
        "Price is R20,100 below budget",
        "Automatic transmission",
        "SUV body type",
        "Mileage is 52,000 km below maximum"
      ],
      "mismatches": []
    },
    {
      "vehicle_id": 3,
      "make": "Toyota",
      "model": "RAV4",
      "year": 2016,
      "price": 239900,
      "match_score": 100,
      "reasons": ["Brand matches: Toyota", "Price is R10,100 below budget", "..."],
      "mismatches": []
    }
  ],
  "criteria": {
    "budget_max": 250000,
    "brand": "Toyota",
    "transmission": "Automatic",
    "body_type": "SUV",
    "max_mileage": 100000
  }
}
```

`criteria` echoes the structured requirements that were actually used — handy for checking how a natural-language `query` was interpreted. `mismatches` lists what a partial match gets wrong (e.g. `"Transmission is Manual, not Automatic"`).

**More examples**

```json
{ "budget_max": 250000, "transmission": "automatic" }
{ "brand": "Toyota" }
{ "budget_max": 200000, "body_type": "Hatchback", "max_mileage": 80000 }
{ "query": "diesel bakkie, ford, max R450 000, under 120k km, 2018 or newer" }
```

The natural-language parser understands amounts like `R250k`, `R250,000`, `R250 000`, `R1.2m`; mileage like `100,000 km` or `under 80k km`; years like `2018 or newer` / `from 2019`; plus brand, transmission, body type and fuel type.

Only **available** vehicles are ever considered for matching.

### `GET /api/v1/vehicles`

Lists vehicles with optional filters and pagination.

| Parameter | Description |
|---|---|
| `brand`, `model` | case-insensitive; brand also resolves aliases/typos |
| `transmission`, `body_type`, `fuel_type` | same accepted values/aliases as above |
| `min_price`, `max_price` | price range (R) |
| `max_mileage` | km |
| `min_year`, `max_year` | year range |
| `available` | `true` / `false` (default: both are listed) |
| `sort_by` | `id` (default), `price`, `mileage`, `year` |
| `order` | `asc` (default), `desc` |
| `page` | default `1` |
| `limit` | default `10`, max `100` |

```
GET /api/v1/vehicles?brand=Toyota
GET /api/v1/vehicles?max_price=250000&transmission=automatic
GET /api/v1/vehicles?page=1&limit=10
GET /api/v1/vehicles?sort_by=price&order=desc&limit=5
```

```json
{
  "page": 1,
  "limit": 10,
  "total": 11,
  "total_pages": 2,
  "items": [
    {
      "id": 1, "make": "Toyota", "model": "Urban Cruiser", "variant": "1.5 XR",
      "year": 2021, "price": 229900, "mileage": 48000, "fuel_type": "Petrol",
      "transmission": "Automatic", "body_type": "SUV", "colour": "White", "availability": true
    }
  ]
}
```

A page beyond the last one returns `200` with an empty `items` list.

### `GET /health`

Returns `{"status": "ok"}`.

## Error handling

Every error is JSON in one consistent shape. Raw Python exceptions and FastAPI's default `{"detail": [...]}` are never exposed.

```json
{
  "error": "validation_error",
  "message": "budget_max must be greater than 0",
  "details": [
    { "field": "budget_max", "message": "budget_max must be greater than 0" }
  ]
}
```

All problems in a request are reported together (`message` joins them with `;`, `details` lists each).

| Status | `error` | When |
|---|---|---|
| `422` | `validation_error` | Negative/zero budget, negative mileage, invalid year, invalid transmission / body type / fuel type, wrong data types (e.g. `"250000"` as a string, `true` as a number), empty request, unknown fields, malformed JSON, missing body, bad pagination parameters, unintelligible `query` |
| `404` | `not_found` | Unknown route |
| `405` | `method_not_allowed` | Wrong HTTP method |
| `500` | `internal_server_error` | Unexpected failure (details are logged server-side, not returned) |

Examples of messages: `transmission must be one of: Automatic, Manual (got 'cvx')`, `max_mileage must be greater than or equal to 0`, `min_year must be between 1980 and 2027`, `Request body is not valid JSON`, `Provide at least one search criterion: budget_max, brand, ...`.

## Matching algorithm

### Scoring

Each requested criterion has a weight, based on the suggested scheme with one addition (minimum year):

| Criterion | Weight |
|---|---|
| Brand matches | 25 |
| Within budget | 25 |
| Transmission matches | 15 |
| Body type matches | 15 |
| Mileage within maximum | 10 |
| Fuel type matches | 10 |
| Year at least `min_year` | 10 |

**Score = points earned ÷ total weight of the criteria the customer actually supplied × 100**, rounded to a whole number.

### Reasoning behind the design decisions

* **Normalising to the requested criteria.** Customers don't have to provide every field, so a fixed total of 100 would unfairly cap vehicles at e.g. 40 when only budget and transmission were requested. Normalising means "satisfies everything asked for" is always 100, and scores are comparable across different kinds of search.
* **Weights.** Brand and budget carry the most weight because they are the criteria customers are least willing to compromise on. Transmission and body type are strong preferences; mileage and fuel type are usually more flexible.
* **Near-misses earn half credit.** A vehicle up to 10% over budget or over the mileage limit gets 50% of that criterion's points, so a R255,000 car outranks a R400,000 one for a R250,000 budget. Beyond 10% it earns nothing. This is deliberate: customers often stretch a little, but a hard cut-off would hide good options.
* **`min_score` (default 50) hides weak matches.** Without a threshold, every vehicle with at least one matching attribute would be returned. A score of 0 is never a match.
* **Deterministic ordering.** Results are sorted by score (highest first); ties are broken by lower price, then lower mileage, then id.
* **Explainability.** Each criterion produces a plain-English message (`Price is R10,000 below budget`, `Mileage is 15,000 km below maximum`), listed under `reasons` when satisfied and `mismatches` otherwise.
* **Availability.** Vehicles with `availability = false` are never returned by the match endpoint.

### Bonus features implemented

| Bonus | Status |
|---|---|
| A — Natural-language search | ✅ `query` field, rule-based parser in `app/services/nlp.py` |
| B — Fuzzy matching | ✅ case-insensitive brand/transmission/body/fuel, aliases (`Auto`, `VW`, `hatch`, `pickup`), small brand typos via `difflib` |
| C — Explainable matching | ✅ `reasons` / `mismatches` with amounts |
| D — Swagger/OpenAPI | ✅ `/docs`, `/redoc`, `/openapi.json` |

## Running the tests

```bash
pip install -r requirements.txt
python -m pytest            # add -v for detail
```

129 tests run in about a second. Each test gets its own in-memory SQLite database populated with a small, known inventory (`tests/conftest.py`), so expected results are exact and tests never touch `vehicles.db`.

| File | Covers |
|---|---|
| `tests/test_match_api.py` | brand, budget, transmission, body type, mileage, fuel, year, multiple criteria, optional criteria, no criteria, no matches, ordering, explanations, fuzzy matching, natural language, valid & invalid requests, missing fields, invalid data types, malformed JSON, error format |
| `tests/test_vehicle_listing.py` | listing, every filter, sorting, pagination (pages complete/disjoint, beyond last page), invalid parameters |
| `tests/test_matching_service.py` | scoring unit tests: weights, normalisation, tolerance boundaries, tie-breaking, brand resolution |
| `tests/test_nlp_and_seed.py` | natural-language parser, seed data (30+ vehicles, valid vocabulary), idempotent seeding |

## Docker

```bash
docker build -t vehicle-matcher .
docker run -p 8000:8000 vehicle-matcher
```

Then open http://localhost:8000/docs.

What happens: the image is based on `python:3.12-slim`, installs dependencies in a cached layer, copies the app, and runs as a non-root user. On startup the app creates the SQLite database in `/data` and seeds it with the sample vehicles.

Useful variations:

```bash
# keep the database between container restarts
docker run -p 8000:8000 -v vehicle-data:/data vehicle-matcher

# use a different database
docker run -p 8000:8000 -e VM_DATABASE_URL=postgresql+psycopg://user:pw@host/db vehicle-matcher

# run the tests inside the container
docker run --rm vehicle-matcher python -m pytest -q
```

## Technical explanation

### Architecture

A small layered application, with each layer having a single job:

```
app/
├── main.py            App creation, startup (create tables + seed), router + error-handler wiring
├── config.py          Settings from environment variables (pydantic-settings)
├── database.py        Engine, session factory, get_db dependency
├── models.py          SQLAlchemy Vehicle model
├── enums.py           Transmission / BodyType / FuelType + alias tables for fuzzy input
├── schemas.py         Pydantic request/response models and all input validation
├── errors.py          Consistent JSON error responses
├── routers/vehicles.py  HTTP layer: the two endpoints (thin; no scoring logic)
├── services/
│   ├── matching.py    Scoring + ranking (pure Python, no HTTP or database knowledge)
│   └── nlp.py         Natural-language → structured criteria
└── seed_data.py       Sample inventory
scripts/seed.py        Seed / reset CLI
tests/                 Pytest suite
```

Request flow for `POST /match`: Pydantic validates the body → the router (optionally) parses `query`, merges explicit fields and resolves the brand → loads available vehicles → `rank_vehicles()` scores and sorts them → the router shapes the response. The scoring code never imports FastAPI and never touches the database, which is why it can be unit-tested directly.

### Database design

A single `vehicles` table with the fields from the brief: `id` (PK), `make`, `model`, `variant`, `year`, `price`, `mileage`, `fuel_type`, `transmission`, `body_type`, `colour`, `availability`.

* Prices are stored as integer rand and mileage as integer km. This avoids floating-point money issues.
* `CHECK` constraints enforce `price >= 0` and `mileage >= 0` at database level as well as in the API.
* Indexes on `make`, `year`, `price`, `fuel_type`, `transmission`, `body_type` and `availability`, i.e. the columns used for filtering the listing endpoint.
* `fuel_type`, `transmission` and `body_type` are stored as canonical strings (`"Automatic"`, `"SUV"`) validated by Python enums, rather than as separate lookup tables or database enums. This keeps the schema portable across SQLite/PostgreSQL/MySQL and avoids a migration for every new value, at the cost of the database not enforcing the vocabulary itself.
* `make` is deliberately kept as a plain column. Normalising makes/models into their own tables would be the next step for a larger system but is more machinery than a 44-row inventory needs.

### Technology choices

| Choice | Why |
|---|---|
| **FastAPI** | Validation, serialisation and OpenAPI docs come from the same type declarations, so docs can't drift from behaviour. Delivers bonus D for free. |
| **SQLAlchemy 2** | Database-agnostic (SQLite now, PostgreSQL by changing one URL), explicit and well understood. |
| **Pydantic 2** | Strict validation (e.g. `"250000"` and `true` are rejected as budgets) with precise error information that the error handler turns into readable messages. |
| **SQLite** | Zero setup, which suits an assessment and Docker demo. Tests use in-memory SQLite. |
| **pydantic-settings** | Twelve-factor configuration via environment variables. |
| **Pytest + FastAPI TestClient** | Fast API-level tests with dependency overrides for an isolated database per test. |
| **Rule-based NL parser (no LLM/NLP library)** | Deterministic, offline, instant and fully testable. An LLM would handle more phrasing but adds cost, latency, nondeterminism and an external dependency. |
| **`difflib` for typos** | Standard library; enough for brand names without adding a fuzzy-matching dependency. |

### Trade-offs

* **Scoring in Python rather than SQL.** The score depends on partial credit, normalisation and explanations that are far easier to express and test in Python. The cost is that every search loads all available vehicles. That is fine for hundreds or a few thousand rows and is the first thing to change at scale (see below).
* **Soft matching instead of hard filtering.** Near-misses are returned with lower scores rather than excluded, which suits a sales context. It means results can include vehicles that don't satisfy every criterion; `mismatches` and `min_score` keep that transparent and controllable.
* **Rule-based NL parsing** covers common phrasing but not everything (e.g. ranges like "between R200k and R250k", negation, model names such as "RAV4" are not understood as criteria).
* **Unknown brands are not an error.** `brand: "Ferrari"` returns zero matches rather than a 422, because a customer asking for a brand the dealership doesn't stock is a legitimate search, not invalid input.
* **No migrations tool.** `create_all` is enough for a single-table assessment project; Alembic would be added before the schema changes in production.
* **No authentication or rate limiting**, as neither was in scope.

### Future improvements

* Alembic migrations and a PostgreSQL deployment via Docker Compose.
* Separate `makes`/`models` tables; vehicle detail (`GET /vehicles/{id}`) and inventory management endpoints.
* Move candidate selection and scoring into the database (below) and add result caching.
* Preference weighting supplied by the customer ("budget matters most").
* Model/variant criteria (e.g. "RAV4") and range queries in the natural-language parser, or an optional LLM-backed parser behind the same interface.
* Authentication, rate limiting, structured logging and metrics.
* CI pipeline running the tests and building the Docker image.

## Final question: 100,000 vehicles and 50,000 searches per day

First, the numbers: 50,000 searches a day averages only **~0.6 requests per second** (perhaps 10–20/s at peak). That is a modest request rate; the real problem is the *cost of each request*. Today every search loads every available vehicle into Python objects and scores them one by one. With 100,000 vehicles that is a full table read plus 100,000 object constructions and score calculations per request, which would take on the order of seconds, hold a worker for that time, and put needless load on the database. Here is what I would change, in order of impact:

1. **Do the work in the database and return only the top N.**  
   Compute the score in SQL (a sum of `CASE WHEN … THEN weight` expressions, including the 10% tolerance), apply `WHERE score >= min_score`, `ORDER BY score DESC, price, mileage, id LIMIT N`, and select only the needed columns. Generate the `reasons` text in Python for just those N rows, not for 100,000. The request then returns almost the same amount of data regardless of inventory size.

2. **Move to PostgreSQL and index for the access pattern.**  
   SQLite allows a single writer and is not designed for concurrent production traffic. PostgreSQL with composite/partial indexes (e.g. a partial index `WHERE availability` on `(make, body_type, transmission, price)`) lets a cheap pre-filter shrink the candidate set before scoring, e.g. "must satisfy at least one of the criteria" or hard limits at a generous tolerance. Keep the planner honest with `EXPLAIN ANALYZE` on realistic data.

3. **Cache.**  
   Many customers will make the same popular searches (e.g. Toyota automatic SUV under R250k). Cache normalised-criteria → result in Redis with a short TTL, invalidated or versioned when inventory changes. Cache the list of distinct makes (currently queried on every request) in memory. Inventory changes slowly relative to read traffic, so hit rates should be high.

4. **Scale out the stateless API.**  
   Run several Uvicorn/Gunicorn workers or containers behind a load balancer, with the database connection pool sized to match. The service is already stateless, so this is straightforward. Add read replicas if reads outgrow one database.

5. **Keyset pagination for the listing endpoint.**  
   `OFFSET` gets slower the deeper the page on a large table. Paginate with a cursor (`WHERE (price, id) > (:last_price, :last_id)`).

6. **Dedicated search infrastructure only if needed.**  
   If scoring becomes richer (free-text model search, typo-tolerant ranking, facets), move to OpenSearch/Elasticsearch fed from the primary database. At 100,000 rows PostgreSQL alone should be sufficient, so I would not add this complexity up front.

7. **Operations.**  
   Rate limiting and abuse protection on the public endpoint, request timeouts, structured logs, latency/error metrics and alerting (p95 of `/match` is the number to watch), load testing (Locust/k6) with 100,000 generated vehicles before and after each change, and inventory ingestion as a batch job or change-data-capture stream rather than ad-hoc writes.

I would measure first: generate 100,000 vehicles, profile `/match`, and make the changes in the order above, stopping when the latency target is met. Steps 1–3 are likely enough for this load.

## Submission details

```
Repository URL:      <add your repository URL>
Candidate Name:      <add your name>
Date Completed:      2 October 2026
Time Spent:          <add your time>
Technologies Used:   Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2, SQLite, Pytest, Docker
Known Limitations:   See below
Additional Features: Natural-language search, fuzzy matching, explainable matching,
                     Swagger/OpenAPI, sorting on the listing endpoint, limit/min_score controls,
                     health endpoint, startup auto-seeding
```

**Known limitations and problems encountered**

* **The Docker image was not built or run in the environment where this project was developed**, because no Docker daemon was available there. The Dockerfile is straightforward, and the identical startup path (create tables → auto-seed → serve) was verified by running the app with `uvicorn` against a fresh database and exercising both endpoints and `/docs`. Please run `docker build -t vehicle-matcher .` once to confirm on your machine.
* **A bug found by the tests during development:** a request such as `{"brand": null}` crashed validation with a `TypeError` (the max-length constraint was being applied to `None`). It was fixed by applying the constraint to the string type only, and the case is now covered by a test.
* The natural-language parser is rule-based and handles common phrasing only (see Trade-offs).
* Scoring runs in Python over all available vehicles, which is appropriate for this inventory size but not for 100,000+ vehicles (see the scaling answer).
* Schema is created with `create_all`; there are no migrations.
#   V e h i c l e r - M a t c h i n g - A P I - P r o j e c t  
 