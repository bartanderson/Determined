"""
Capture route -- HTTP boundary only.

Parses the request, validates input, calls the extractor service,
and returns a response. No business logic here.

The extractor stubs (extract_metadata, extract_full_content) are the
direct-call frontier Determined shows on first ingest of this project.
"""
from flask import Blueprint, request, jsonify, render_template_string
from services import extractor

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
    if not (url.startswith("http://") or url.startswith("https://")):
        return render_template_string(_FORM, error="Must be an http/https URL."), 400

    try:
        entry = extractor.extract(url)
    except Exception as exc:
        return render_template_string(_FORM, error=str(exc)), 400

    # Storage not wired yet -- next step is adding queries.insert_entry.
    return render_template_string(_FORM, entry=entry)
