# tests/regression/test_classify_role_flask.py
#
# Ensures Flask/Blueprint route files are classified as entry_point,
# not module. RM18 Gap 2 fix.

from pathlib import Path
from determined.ingestion.parse_ast import _classify_role


def _path(name):
    return Path("examples") / "web" / name


# --- Flask route detection ---

def test_blueprint_route_is_entry_point():
    src = """
from flask import Blueprint
bp = Blueprint('browse', __name__)

@bp.route('/entries')
def list_entries():
    return []
"""
    assert _classify_role(_path("browse.py"), src) == "entry_point"


def test_app_route_is_entry_point():
    src = """
from flask import Flask
app = Flask(__name__)

@app.route('/health')
def health():
    return 'ok'
"""
    assert _classify_role(_path("app.py"), src) == "entry_point"


def test_route_with_methods_is_entry_point():
    src = """
@capture_bp.route('/capture', methods=['GET', 'POST'])
def capture():
    pass
"""
    assert _classify_role(_path("capture.py"), src) == "entry_point"


def test_plain_module_not_entry_point():
    src = """
def find_connections(entry_id):
    return []
"""
    assert _classify_role(_path("linker.py"), src) == "module"


def test_decorated_but_not_route():
    src = """
@login_required
def profile():
    pass
"""
    # login_required has no .route( pattern — stays module
    assert _classify_role(_path("views.py"), src) == "module"


# --- Existing role checks still pass ---

def test_init_file():
    assert _classify_role(Path("pkg") / "__init__.py", "") == "init"


def test_test_file():
    assert _classify_role(Path("tests") / "test_foo.py", "") == "test"


def test_main_sentinel():
    assert _classify_role(_path("run.py"), "if __name__ == '__main__': main()") == "entry_point"


def test_config_file():
    assert _classify_role(_path("config.py"), "") == "config"
