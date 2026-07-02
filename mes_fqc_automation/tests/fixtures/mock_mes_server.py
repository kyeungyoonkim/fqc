"""A tiny fake MES web app used only for integration-testing src/scraper.py.

It intentionally mimics the *shape* of a real MES: a login form that sets a
session cookie, and a Daily FQC page (behind login) rendering E03/E19/T11 and
an overall defect rate - so we can prove the generic Playwright-based
scraper in src/scraper.py actually works end-to-end, without needing access
to a real CTV/DLT/JC system.
"""
from __future__ import annotations

from flask import Flask, redirect, request, session

app = Flask(__name__)
app.secret_key = "test-secret"

VALID_USER = "demo_user"
VALID_PASS = "demo_pass"

FQC_DATA = {"E03": 1.23, "E19": 0.45, "T11": 2.10, "OVERALL": 1.02}

LOGIN_PAGE = """
<html><body>
<form method="post">
  <input id="userId" name="username" type="text" />
  <input id="password" name="password" type="password" />
  <button id="loginBtn" type="submit">Login</button>
</form>
</body></html>
"""

FQC_PAGE = f"""
<html><body>
<div id="gnbUserMenu">Welcome, demo_user</div>
<table id="fqcTable">
  <tr data-line="E03"><td>E03</td><td class="defect-rate">{FQC_DATA['E03']}%</td></tr>
  <tr data-line="E19"><td>E19</td><td class="defect-rate">{FQC_DATA['E19']}%</td></tr>
  <tr data-line="T11"><td>T11</td><td class="defect-rate">{FQC_DATA['T11']}%</td></tr>
  <tfoot><tr><td colspan="2" class="total-defect-rate">{FQC_DATA['OVERALL']}%</td></tr></tfoot>
</table>
</body></html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == VALID_USER and request.form.get("password") == VALID_PASS:
            session["logged_in"] = True
            return redirect("/quality/dailyFqc")
        return "Invalid credentials", 401
    return LOGIN_PAGE


@app.route("/quality/dailyFqc")
def daily_fqc():
    if not session.get("logged_in"):
        return redirect("/login")
    return FQC_PAGE


if __name__ == "__main__":
    app.run(port=5055)
