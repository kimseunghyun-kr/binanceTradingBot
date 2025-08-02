import os, time, sys


def _attach():
    if os.getenv("PYCHARM_ATTACH") != "1":
        print("[debug] PYCHARM_ATTACH != 1; skipping", file=sys.stderr, flush=True)
        return
    try:
        import pydevd_pycharm
    except Exception as e:
        print("[debug] pydevd not available:", repr(e), file=sys.stderr, flush=True)
        return

    # Skip only if THIS process is already attached
    if getattr(pydevd_pycharm, "get_global_debugger", None) is not None:
        print("[debug] debugger already attached; skipping", file=sys.stderr, flush=True)
        return

    host = os.getenv("PYCHARM_HOST", "host.docker.internal")
    port = int(os.getenv("PYCHARM_PORT", "5678"))
    retries = int(os.getenv("PYCHARM_RETRIES", "20"))
    delay = float(os.getenv("PYCHARM_DELAY", "0.5"))
    suspend = os.getenv("PYCHARM_SUSPEND", "0") == "1"  # ← flip to 1 to force a pause

    for i in range(retries):
        try:
            print(f"[debug] attempting attach to {host}:{port} (try {i+1}/{retries})", file=sys.stderr, flush=True)
            pydevd_pycharm.settrace(
                host, port=port,
                stdoutToServer=True, stderrToServer=True,
                suspend=suspend,
                patch_multiprocessing=True,
            )
            print(f"[debug] Attached to PyCharm at {host}:{port}", file=sys.stderr, flush=True)
            return
        except Exception as e:
            print(f"[debug] attach failed: {repr(e)}; retrying…", file=sys.stderr, flush=True)
            time.sleep(delay)
    print(f"[debug] Failed to attach to {host}:{port}", file=sys.stderr, flush=True)

_attach()
