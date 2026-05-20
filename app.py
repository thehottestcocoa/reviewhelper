"""Flask web app for 체험단 알리미."""
from __future__ import annotations

import os
import threading
import warnings
warnings.filterwarnings("ignore")

from dataclasses import asdict
from pathlib import Path

import yaml
from flask import Flask, jsonify, render_template, request

from distance import enrich_distance
import filters
from kakao_auth import ensure_valid_token
from notifier import send
from scrapers import scrape_dinnerqueen, scrape_gangnam, scrape_reviewnote

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
CONFIG_PATH = Path(__file__).parent / "config.yaml"

_last_campaigns = []   # Campaign objects (for send)
_last_results: list[dict] = []   # dicts (for JSON)
_scrape_running = False
_scrape_done = False
_scrape_errors: list[str] = []
_scrape_total = 0


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def _campaign_to_dict(c) -> dict:
    d = asdict(c)
    d["prob_label"] = c.prob_label
    d["ratio"] = round(c.ratio, 2) if c.ratio != float("inf") else 99
    d["benefit_amount"] = c.benefit_amount
    d["score_label"] = _score_label(c.ratio)
    d["channel"] = c.channel
    d["review_days"] = c.review_days
    return d


def _score_label(ratio: float) -> str:
    if ratio < 1:
        return "fire"
    if ratio < 2:
        return "star"
    if ratio < 5:
        return "normal"
    return "tough"


@app.route("/")
def index():
    config = load_config()
    return render_template("index.html", config=config)


def _do_scrape(config: dict) -> None:
    global _last_campaigns, _last_results, _scrape_running, _scrape_done, _scrape_errors, _scrape_total
    try:
        loc = config.get("my_location", {})
        my_lat = loc.get("lat", 37.5563)
        my_lng = loc.get("lng", 126.9723)
        filt = config.get("filter", {})
        max_deadline = filt.get("max_deadline_days", 2)
        max_ratio = filt.get("max_ratio", 3.0)
        include_delivery = filt.get("include_delivery", False)
        max_results = filt.get("max_results", None)
        cities = config.get("preferred_cities", [])
        districts = config.get("preferred_districts", [])
        home_districts = config.get("home_districts", [])
        categories = config.get("categories", [])
        weights = config.get("scoring_weights", {
            "probability": 0.5, "benefit": 0.25, "distance": 0.15, "home_bonus": 0.10,
        })

        all_campaigns = []
        errors = []

        try:
            rn = scrape_reviewnote(max_deadline_days=max_deadline + 1)
            all_campaigns += rn
        except Exception as e:
            errors.append(f"리뷰노트: {e}")

        try:
            dq_cfg = config.get("dinnerqueen", {})
            dq = scrape_dinnerqueen(
                cities=["서울"],
                max_deadline_days=max_deadline,
                email=dq_cfg.get("email", ""),
                password=dq_cfg.get("password", ""),
            )
            all_campaigns += dq
        except Exception as e:
            errors.append(f"디너의여왕: {e}")

        try:
            gn = scrape_gangnam()
            all_campaigns += gn
        except Exception as e:
            errors.append(f"강남맛집: {e}")

        enrich_distance(all_campaigns, my_lat, my_lng)

        picked = filters.apply(
            all_campaigns,
            districts=districts,
            campaign_types=["방문"],
            categories=categories,
            max_deadline_days=max_deadline,
            max_ratio=max_ratio,
            include_delivery=include_delivery,
            cities=cities,
            weights=weights,
            max_results=max_results,
            home_districts=home_districts,
        )

        _last_campaigns = picked
        _last_results = [_campaign_to_dict(c) for c in picked]
        _scrape_errors = errors
        _scrape_total = len(all_campaigns)
    finally:
        _scrape_running = False
        _scrape_done = True


@app.route("/api/run", methods=["POST"])
def api_run():
    global _scrape_running, _scrape_done
    if _scrape_running:
        return jsonify({"status": "running"})
    _scrape_running = True
    _scrape_done = False
    config = load_config()
    t = threading.Thread(target=_do_scrape, args=(config,), daemon=True)
    t.start()
    return jsonify({"status": "started"})


@app.route("/api/status")
def api_status():
    if _scrape_running:
        return jsonify({"status": "running"})
    if _scrape_done:
        return jsonify({
            "status": "done",
            "campaigns": _last_results,
            "total_scraped": _scrape_total,
            "errors": _scrape_errors,
        })
    return jsonify({"status": "idle"})


@app.route("/api/campaigns")
def api_campaigns():
    return jsonify({"campaigns": _last_results})


@app.route("/api/send", methods=["POST"])
def api_send():
    if not _last_campaigns:
        return jsonify({"ok": False, "error": "먼저 수집하기를 실행하세요."}), 400
    config = load_config()
    try:
        token = ensure_valid_token(config)
        send(_last_campaigns, token)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.json or {}
    config = load_config()

    filt = config.setdefault("filter", {})
    if "max_deadline_days" in data:
        filt["max_deadline_days"] = int(data["max_deadline_days"])
    if "max_ratio" in data:
        filt["max_ratio"] = float(data["max_ratio"])
    if "max_results" in data:
        v = data["max_results"]
        filt["max_results"] = int(v) if v else None
    if "include_delivery" in data:
        filt["include_delivery"] = bool(data["include_delivery"])
    if "preferred_districts" in data:
        config["preferred_districts"] = [d.strip() for d in data["preferred_districts"].split(",") if d.strip()]
    if "home_districts" in data:
        config["home_districts"] = [d.strip() for d in data["home_districts"].split(",") if d.strip()]
    if "dinnerqueen_email" in data:
        config.setdefault("dinnerqueen", {})["email"] = data["dinnerqueen_email"].strip()
    if "dinnerqueen_password" in data:
        config.setdefault("dinnerqueen", {})["password"] = data["dinnerqueen_password"].strip()

    save_config(config)
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
