from flask import Blueprint, request, render_template
from services import searcher

search_bp = Blueprint("search", __name__)


@search_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    results = searcher.semantic_search(query) if query else []
    return render_template("search.html", query=query, results=results)
