"""
Search route -- HTTP boundary only.
"""
from flask import Blueprint, request, render_template_string
from services import searcher

search_bp = Blueprint("search", __name__)

_TEMPLATE = """
<!doctype html>
<title>Commonplace - Search</title>
<form method=get>
  <input name=q value="{{ query }}" size=60> <button type=submit>Search</button>
</form>
{% if results %}
  {% for r in results %}<p>{{ r.title }} -- {{ r.source_url }}</p>{% endfor %}
{% elif query %}
  <p>No results.</p>
{% endif %}
"""


@search_bp.route("/search", methods=["GET"])
def search():
    query = request.args.get("q", "").strip()
    results = searcher.semantic_search(query) if query else []
    return render_template_string(_TEMPLATE, query=query, results=results)
