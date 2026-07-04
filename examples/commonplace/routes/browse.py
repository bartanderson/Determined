from flask import Blueprint, render_template, abort
from storage import queries

browse_bp = Blueprint("browse", __name__)


@browse_bp.route("/")
def index():
    entries = queries.list_entries(limit=20)
    return render_template("index.html", entries=entries)


@browse_bp.route("/entry/<int:entry_id>")
def entry_detail(entry_id):
    entry = queries.get_entry(entry_id)
    if not entry:
        abort(404)
    tags = queries.get_entry_tags(entry_id)
    connections = queries.get_connections(entry_id)
    return render_template("entry.html", entry=entry, tags=tags, connections=connections)
