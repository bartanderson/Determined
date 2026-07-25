from flask import Blueprint, jsonify, request, abort
from storage import queries
from services import searcher

api_bp = Blueprint("api", __name__)


@api_bp.route("/entries")
def list_entries():
    entries = queries.list_entries(limit=50)
    return jsonify([dict(e) for e in entries])


@api_bp.route("/entries/<int:entry_id>")
def get_entry(entry_id):
    entry = queries.get_entry(entry_id)
    if not entry:
        abort(404)
    tags = queries.get_entry_tags(entry_id)
    return jsonify({**dict(entry), "tags": [dict(t) for t in tags]})


@api_bp.route("/search")
def search():
    query = request.args.get("q", "")
    return jsonify(searcher.search(query))
