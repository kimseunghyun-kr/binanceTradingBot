# Developer Quickstart (EN)

This project is a FastAPI + Celery service for running trading strategy backtests via web and distributed worker tasks.

---

## Developer Quickstart

### 1. Start the API Server

```bash
python run_local.py
```

* This loads environment variables based on your profile (see `.env.*` files).

### 2. Start the Celery Worker(s)

**Standard operation:**

```bash
python worker.py
```

* This runs a Celery worker that processes background tasks.
* Make sure Redis is running locally if required.

**For debugging (PyCharm, etc):**

* Open `worker.py` in your IDE.
* Set breakpoints as needed.
* Run or debug `worker.py` in your IDE.
* **Note:** Breakpoints are hit when the worker processes a task (not when API is called).

### 3. Access the API Swagger UI

* Go to: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* Use the "Try it out" button to test endpoints, or use Postman/curl.

### 4. Submit a Backtest Job

* Use `/backtest` endpoint (Swagger UI or Postman).
* Submit your configuration.
* The API returns a `task_id`.

### 5. Check Task Status and Results

* Use `/tasks/{task_id}` (GET) to check status/result.
* Status: `pending`, `started`, `success`, `failure`.

### 6. Debugging and Logs

* Results show in the browser/Postman when ready.
* **Debugging:**

    * Breakpoints in your IDE are hit by the Celery worker **when it runs the task**.
    * Errors/stack traces print to the terminal or IDE console running `worker.py`.
    * If a task fails or hangs, check worker logs/console.
    * Error handling is minimal; failed tasks may hang or show minimal error info.

### 7. Notes

* Only `/backtest` is fully tested.
* Robust error handling is planned for future updates.
* If you get issues:

    * Confirm both `run_local.py` and `worker.py` are running.
    * Check that dependencies (Redis, MongoDB, etc) are available.
    * Review worker logs for stack traces.
    * If tasks hang, restart the worker.