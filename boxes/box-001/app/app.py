#!/usr/bin/env python3
"""CyberForge Box 001 — inventory portal (lab application)."""

import subprocess

from flask import Flask, abort, render_template_string, request
from markupsafe import escape

APP_NAME = "CyberForge Box 001"
APP_VERSION = "1.0"
INVENTORY_FILE = "/app/data/inventory.txt"

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }} — {{ app_name }}</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0f14;
      --panel: #121820;
      --line: #2a3644;
      --text: #e7eef6;
      --muted: #93a4b7;
      --accent: #3dd6c6;
      --danger: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header, main, footer { width: min(860px, calc(100% - 2rem)); margin: 0 auto; }
    header {
      padding: 1.5rem 0 1rem;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      align-items: baseline;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .brand { font-weight: 700; letter-spacing: 0.04em; }
    .version { color: var(--muted); font-size: 0.9rem; }
    main { padding: 1.5rem 0 3rem; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 1.25rem 1.4rem;
    }
    h1 { margin: 0 0 0.6rem; font-size: 1.6rem; }
    p { color: var(--muted); line-height: 1.5; }
    form { display: flex; gap: 0.6rem; margin: 1rem 0; }
    input[type=text] {
      flex: 1;
      padding: 0.7rem 0.8rem;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #0b0f14;
      color: var(--text);
    }
    button {
      border: 0;
      border-radius: 8px;
      padding: 0.7rem 1rem;
      background: var(--accent);
      color: #04221e;
      font-weight: 700;
      cursor: pointer;
    }
    pre {
      overflow: auto;
      background: #070b10;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 1rem;
      color: #d5f5ef;
    }
    .error { color: var(--danger); }
    nav { margin-top: 1rem; display: flex; gap: 1rem; }
    footer { color: var(--muted); font-size: 0.85rem; padding-bottom: 1.5rem; }
  </style>
</head>
<body>
  <header>
    <div class="brand">{{ app_name }}</div>
    <div class="version">Version {{ version }}</div>
  </header>
  <main>
    <section class="panel">
      {{ body|safe }}
      <nav>
        <a href="/">Home</a>
        <a href="/search">Search</a>
        <a href="/admin">Admin</a>
      </nav>
    </section>
  </main>
  <footer>Local CyberForge lab — isolated training environment.</footer>
</body>
</html>
"""


def page(title: str, body: str) -> str:
    return render_template_string(
        PAGE,
        title=title,
        body=body,
        app_name=APP_NAME,
        version=APP_VERSION,
    )


@app.get("/")
def home():
    body = """
      <h1>Internal asset inventory</h1>
      <p>Search the lab inventory for internal hostnames used by this box.</p>
      <p>This portal belongs to <strong>CyberForge Box 001</strong>.</p>
    """
    return page("Home", body)


@app.get("/robots.txt")
def robots():
    return (
        "User-agent: *\nDisallow: /admin\nDisallow: /search\n",
        200,
        {"Content-Type": "text/plain; charset=utf-8"},
    )


@app.get("/search")
def search():
    query = request.args.get("q", "")
    result_block = ""
    if query:
        # Lab-only: the query is passed to the shell on purpose so the
        # training path can start from this endpoint. Do not reuse this
        # pattern outside an isolated local lab.
        command = f"grep -i {query} {INVENTORY_FILE}"
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            if not output.strip():
                output = "No matching assets."
        except subprocess.TimeoutExpired:
            output = "Search timed out."
        result_block = f"<h2>Results</h2><pre>{escape(output[:32000])}</pre>"

    body = f"""
      <h1>Asset search</h1>
      <p>Look up an internal hostname fragment.</p>
      <form method="get" action="/search">
        <input type="text" name="q" value="{escape(query)}" placeholder="target" autofocus>
        <button type="submit">Search</button>
      </form>
      {result_block}
    """
    return page("Search", body)


@app.get("/admin")
def admin():
    abort(403)


@app.errorhandler(403)
def forbidden(_error):
    body = """
      <h1 class="error">Forbidden</h1>
      <p>Administration is restricted to internal operators.</p>
      <p>Deployments are performed from this application host.</p>
    """
    return page("Admin", body), 403


if __name__ == "__main__":
    # Bind all interfaces inside the container; compose publishes 127.0.0.1 only.
    app.run(host="0.0.0.0", port=5000, debug=False)
