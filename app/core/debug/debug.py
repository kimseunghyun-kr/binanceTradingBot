import os, time, sys

def _attach():
    if os.getenv("PYCHARM_ATTACH") != "1":
        print("[sitecustomize] PYCHARM_ATTACH != 1; skipping", file=sys.stderr, flush=True)
        return
    try:
        import pydevd_pycharm, pydevd
    except Exception as e:
        print("[sitecustomize] pydevd not available:", repr(e), file=sys.stderr, flush=True)
        return

    # Skip only if THIS process is already attached
    if getattr(pydevd, "get_global_debugger", None) and pydevd.get_global_debugger() is not None:
        print("[sitecustomize] debugger already attached; skipping", file=sys.stderr, flush=True)
        return

    host = os.getenv("PYCHARM_HOST", "host.docker.internal")
    port = int(os.getenv("PYCHARM_PORT", "5678"))
    retries = int(os.getenv("PYCHARM_RETRIES", "20"))
    delay = float(os.getenv("PYCHARM_DELAY", "0.5"))
    suspend = os.getenv("PYCHARM_SUSPEND", "0") == "1"  # ← flip to 1 to force a pause

    for i in range(retries):
        try:
            print(f"[sitecustomize] attempting attach to {host}:{port} (try {i+1}/{retries})", file=sys.stderr, flush=True)
            pydevd_pycharm.settrace(
                host, port=port,
                stdoutToServer=True, stderrToServer=True,
                suspend=suspend,
                patch_multiprocessing=True,
            )
            print(f"[sitecustomize] Attached to PyCharm at {host}:{port}", file=sys.stderr, flush=True)
            return
        except Exception as e:
            print(f"[sitecustomize] attach failed: {repr(e)}; retrying…", file=sys.stderr, flush=True)
            time.sleep(delay)
    print(f"[sitecustomize] Failed to attach to {host}:{port}", file=sys.stderr, flush=True)

_attach()
