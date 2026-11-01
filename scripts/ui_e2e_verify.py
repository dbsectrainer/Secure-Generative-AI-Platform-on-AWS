#!/usr/bin/env python3
"""
Playwright E2E verification for the local RAG frontend.

Requires the local doubles (:9000), SAM API (:3000), and frontend proxy (:8080)
to be running. Captures desktop/mobile screenshots and browser console/network
failures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    evidence = Path(args.output_dir)
    screenshots = evidence / "screenshots"
    results_dir = evidence / "test-results"
    screenshots.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    console_lines: list[str] = []
    failures: list[str] = []
    checks: list[dict[str, object]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        desktop = browser.new_context(viewport={"width": 1440, "height": 1100}, color_scheme="dark")
        page = desktop.new_page()
        page.on("console", lambda message: console_lines.append(f"{message.type}: {message.text}"))
        page.on("pageerror", lambda error: failures.append(f"pageerror: {error}"))
        page.on("requestfailed", lambda request: failures.append(f"requestfailed: {request.url}"))
        page.goto(args.frontend_url, wait_until="domcontentloaded")
        page.screenshot(path=str(screenshots / "ui-empty-state.png"), full_page=False)
        checks.append({"name": "empty_state_visible", "passed": page.locator("#empty-state").is_visible()})

        page.locator("#load-token").click()
        page.wait_for_function(
            "() => document.getElementById('token').value.length > 100",
            timeout=30_000,
        )
        checks.append({"name": "local_token_loaded", "passed": True})

        page.locator("#query").fill("Summarize the security controls")
        page.locator("#run").click()
        page.locator("#response-status").filter(has_text="OK").wait_for(timeout=60_000)
        page.locator("#output").wait_for(state="visible", timeout=10_000)
        output = page.locator("#output").inner_text()
        checks.append(
            {
                "name": "rag_answer_rendered",
                "passed": "Based on the retrieved policy excerpts" in output,
                "detail": output[:180],
            }
        )
        metrics = {
            "model": page.locator("#metric-model").inner_text(),
            "chunks": page.locator("#metric-chunks").inner_text(),
            "latency": page.locator("#metric-latency").inner_text(),
        }
        checks.append({"name": "metrics_rendered", "passed": metrics["chunks"] != "—", "detail": metrics})
        page.screenshot(path=str(screenshots / "ui-query-desktop.png"), full_page=True)
        desktop.close()

        mobile = browser.new_context(
            viewport={"width": 390, "height": 844},
            color_scheme="dark",
            is_mobile=True,
            has_touch=True,
        )
        mobile_page = mobile.new_page()
        mobile_page.on("console", lambda message: console_lines.append(f"{message.type}: {message.text}"))
        mobile_page.on("pageerror", lambda error: failures.append(f"pageerror: {error}"))
        mobile_page.on("requestfailed", lambda request: failures.append(f"requestfailed: {request.url}"))
        mobile_page.goto(args.frontend_url, wait_until="domcontentloaded")
        mobile_page.locator("#load-token").click()
        mobile_page.wait_for_function(
            "() => document.getElementById('token').value.length > 100",
            timeout=30_000,
        )
        mobile_page.locator("#query").fill("Summarize the security controls")
        mobile_page.locator("#run").click()
        mobile_page.locator("#response-status").filter(has_text="OK").wait_for(timeout=60_000)
        mobile_page.locator("#output").wait_for(state="visible", timeout=10_000)
        mobile_page.screenshot(path=str(screenshots / "ui-query-mobile.png"), full_page=True)
        checks.append(
            {
                "name": "mobile_query_rendered",
                "passed": mobile_page.locator("#output").is_visible(),
            }
        )
        mobile.close()
        browser.close()

    report = {
        "frontend_url": args.frontend_url,
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "total": len(checks),
        "console_entries": len(console_lines),
        "failures": failures,
    }
    (results_dir / "ui-e2e-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (results_dir / "ui-console.log").write_text("\n".join(console_lines + failures) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
