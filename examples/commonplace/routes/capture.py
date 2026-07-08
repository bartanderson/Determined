from flask import Blueprint, request, redirect, url_for, render_template, flash, current_app
from utils.url import validate_url, normalize
from services import extractor, tagger
from services.pipeline import enrich_entry
from storage import queries

capture_bp = Blueprint("capture", __name__)


@capture_bp.route("/capture", methods=["GET"])
def capture_form():
    return render_template("capture.html")


@capture_bp.route("/capture", methods=["POST"])
def capture():
    entry_type = request.form.get("type", "note")
    content = request.form.get("content", "").strip()
    raw_url = request.form.get("url", "").strip()
    manual_tags = [t.strip() for t in request.form.get("tags", "").split(",") if t.strip()]

    # DESIGN TENSION: URL validation here duplicates utils/url.py validate_url.
    # Two enforcement points for the same rule.
    if entry_type == "url":
        if not validate_url(raw_url):
            flash("Invalid URL.")
            return render_template("capture.html"), 400
        raw_url = normalize(raw_url)
        try:
            extracted = extractor.extract(raw_url)
        except Exception as e:
            flash(f"Could not fetch URL: {e}")
            return render_template("capture.html"), 400
        content = extracted["content"]
        title = extracted["title"]
        source_url = extracted["source_url"]
        excerpt = extracted["excerpt"]
    else:
        title = request.form.get("title", "").strip() or None
        source_url = raw_url or None
        excerpt = content[:200] if content else None

    if not content:
        flash("Content is required.")
        return render_template("capture.html"), 400

    entry_id = queries.insert_entry(entry_type, content, title, source_url, excerpt)

    # enrich_entry is the chain-middle: called here (chain-head), calls
    # find_connections and suggest_tags (chain-tail stubs).
    all_entries = queries.list_entries(limit=200)
    llm_endpoint = current_app.config.get("LLM_ENDPOINT")
    enriched = enrich_entry({"id": entry_id, "content": content}, all_entries, llm_endpoint=llm_endpoint)

    if current_app.config.get("TAGGING_ENABLED"):
        suggested = tagger.suggest_tags(content, endpoint=llm_endpoint)
        for tag_name in suggested:
            tag_id = queries.insert_tag(tag_name, source="llm")
            queries.link_tag(entry_id, tag_id)

    for tag_name in manual_tags:
        tag_id = queries.insert_tag(tag_name, source="manual")
        queries.link_tag(entry_id, tag_id)

    return redirect(url_for("browse.entry_detail", entry_id=entry_id))
