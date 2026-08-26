#!/usr/bin/env python3
"""
Serve the case-study HTML viewer, the same way `python app.py` serves the
live simulation playground at templates/index.html.

    python case_studies/serve.py            # binds 0.0.0.0:5050, serves html/index.html
    python case_studies/serve.py --port 9000

Just like app.py, this binds to 0.0.0.0 and prints the URL — it does not
need to actually pop a browser window itself. On a local machine, run it and
open the printed URL. Over VS Code Remote-SSH (the same way you already
reach app.py's UI), VS Code auto-detects the newly-listening port and shows
an "Open in Browser" notification / lists it in the PORTS tab — click that,
no separate forwarding step needed. Over plain SSH, forward the port
yourself: `ssh -L 5050:localhost:5050 <host>`.
"""
import argparse
import threading
import webbrowser
from pathlib import Path

from flask import Flask, send_from_directory

BASE = Path(__file__).resolve().parent
HTML_DIR = BASE / "html"

app = Flask(__name__, static_folder=str(HTML_DIR), static_url_path="")


@app.route("/")
def root():
    return send_from_directory(HTML_DIR, "index.html")


def _try_open_browser(url: str) -> None:
    """Best-effort local browser launch — silently does nothing on a
    headless remote server (no $DISPLAY), which is expected and harmless."""
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=5050, help="port to bind (default: 5050)")
    ap.add_argument("--host", default="0.0.0.0", help="host to bind (default: 0.0.0.0)")
    ap.add_argument("--no-open", action="store_true", help="skip the local webbrowser.open() attempt")
    args = ap.parse_args()

    if not (HTML_DIR / "index.html").exists():
        raise SystemExit(
            f"{HTML_DIR / 'index.html'} not found — run `python case_studies/render.py` first."
        )

    url = f"http://localhost:{args.port}/"
    print(f"Case studies serving at {url}")
    print("If you're on VS Code Remote-SSH: check the PORTS tab / the auto-forward")
    print(f"notification for port {args.port} and click 'Open in Browser'.")
    print("If you're on plain SSH: `ssh -L %d:localhost:%d <host>` from your local machine, "
          "then open the URL above there." % (args.port, args.port))

    if not args.no_open:
        threading.Timer(0.8, _try_open_browser, args=(url,)).start()

    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
