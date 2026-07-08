"""
Capture route -- HTTP boundary only.

Parses the request, validates input, calls the extractor service,
and returns a response. No business logic here.

The extractor stubs (extract_metadata, extract_full_content) are the
direct-call frontier Determined shows on first ingest of this project.
"""
from flask import Blueprint, request, jsonify, render_template_string
from services import extractor
from services import pipeline
from services.processor import run_processors
from storage import queries
from utils.validator import validate_url, validate_entry

capture_bp = Blueprint("capture", __name__)

_FORM = """
<!doctype html>
<title>Commonplace</title>
<form method=post>
  URL: <input name=url size=60> <button type=submit>Capture</button>
</form>
{% if entry %}<p>Captured: {{ entry.title }}</p>{% endif %}
{% if error %}<p style=color:red>{{ error }}</p>{% endif %}
"""


@capture_bp.route("/", methods=["GET"])
def index():
    return render_template_string(_FORM)


@capture_bp.route("/capture", methods=["POST"])
def capture():
    url = request.form.get("url", "").strip()
    if not url:
        return render_template_string(_FORM, error="URL is required."), 400
    if not validate_url(url):
        return render_template_string(_FORM, error="Must be an http/https URL."), 400

    try:
        entry = extractor.extract(url)
    except Exception as exc:
        return render_template_string(_FORM, error=str(exc)), 400

    entry = run_processors(entry)
    entry = pipeline.enrich_entry(entry, all_entries=[])
    queries.insert_entry(entry)
    return render_template_string(_FORM, entry=entry)
