# Binance Trading Bot — FastAPI + Celery Backtesting Platform

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg) ![FastAPI](https://img.shields.io/badge/FastAPI-async-green) ![Celery](https://img.shields.io/badge/Celery-5.x-yellow)

## Overview

This project is a robust, modular backtesting platform for trading strategies. It combines **FastAPI** for web-based
orchestration and **Celery** for distributed and asynchronous execution of computationally heavy backtest tasks. It is
designed for flexibility, developer productivity, and scaling to large symbol universes (e.g., Binance USDT pairs).

> **⚠️ Project status:**
>
> This project is **not even pre-alpha** and is currently in its **first development iteration**. Many features are
> planned, but only core Celery task orchestration and the controller-service pipeline are confirmed to function at a
> basic level. Symbol query/filtering and core business logic are **not production-ready nor tested**.

* **Technology stack:** Python, FastAPI, Celery, Redis, MongoDB, Pydantic, Pandas
* **Key features:**

    * Submit and track custom trading strategy backtests over HTTP
    * Fully async background workers (Celery)
    * Symbol universe can be filtered, queried, or set dynamically (**symbol query feature under development**)
    * Swagger UI for interactive exploration and manual runs
    * Debug-friendly: run everything locally, debug in PyCharm/VSCode
    * Modular strategy/service design for easy extension

## Features & Project Status

* **Confirmed Working:**

    * Celery background task system
    * Controller → Service pipeline (`backtest.py` endpoint end-to-end call)
* **Under Development:**

    * Symbol query/advanced filtering (currently not production ready)
    * Core business logic for strategies/backtest results (business computation NOT verified)

## Usage Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

* Requires Python 3.10+
* Make sure Redis and MongoDB are running locally (default configs)

### 2. Configure Environment

* Copy `.env.example` or set up your `.env`, `.env.development`, `.env.production` as needed
* Edit API keys and settings in `app/pydanticConfig/settings.py` or your `.env` files

### 3. Start API Server

```bash
python run_local.py
```

* FastAPI will load at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Start Celery Worker(s)

```bash
python worker.py
```

* For debugging, run `worker.py` in PyCharm/VSCode with breakpoints
* Worker logs appear in `logs/worker.log`

### 5. Submit a Backtest

* Use the Swagger UI or Postman:

    * `/backtest` to start a job (returns a `task_id`)
    * `/tasks/{task_id}` to get result/status
* Symbol filtering/query feature is under development (currently only static symbol set supported)

### 6. Debugging

* Worker breakpoints are triggered **only in the Celery worker**
* Stack traces and errors show in the worker's log or console
* If a task hangs, restart the worker

## Advanced Usage (Planned)

### Symbol Selection & Querying

* `symbols`: List of explicit trading pairs (e.g., `["BTCUSDT", "ETHUSDT"]`)
* `symbol_query`: (Planned) SQL-like or sandboxed Python filter — **not yet working**
* Defaults to all filtered/allowed symbols (`ANALYSIS_SYMBOLS`)

### Debugging in IDE

* Place breakpoints in worker or service code
* Run `worker.py` in debug mode
* Submit tasks from Swagger/Postman to trigger code

## Directory Structure

```
.
├── app/
│   ├── core/
│   │   └── celery_app.py          # Celery app & autodiscover
│   ├── pydanticConfig/
│   │   └── settings.py           # Config, .env logic
│   ├── tasks/
│   │   ├── __init__.py           # Imports all task modules
│   │   ├── BackTestTask.py       # Main backtest task
│   │   └── ...                   # Other tasks
│   ├── services/
│   │   └── ...                   # Strategy, backtest, utils
│   └── ...
├── worker.py                     # Entrypoint for Celery worker
├── run_local.py                  # Entrypoint for FastAPI server
└── requirements.txt
```

## Troubleshooting

* **Tasks not running:** Ensure both server and worker are up, and that `ANALYSIS_SYMBOLS` is populated
* **KeyError or missing task:** Check `app/tasks/__init__.py` imports all task modules; restart worker
* **No breakpoints hit:** Remember: worker code (not API server) runs the backtest logic
* **Pending/long tasks:** Some error paths are not robust; check worker log and consider a restart

## Feedback & Contribution

* MVP quality: PRs and feedback are welcome!
* Robust error handling, more endpoints, and richer strategy libraries planned
* See `Developer Quickstart` section above (or `README.KR.md` for Korean)

---

Happy backtesting!
