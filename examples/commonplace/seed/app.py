"""
Commonplace -- seed state.

This is the starting point for the guided Determined journey.
The application can run but the extractor stubs return empty data.
Determined's first read of this project shows the frontier clearly:
two direct-call stubs in extractor.py are the only unimplemented work.
"""
from flask import Flask
from storage.db import init_db
from routes.capture import capture_bp
from routes.search import search_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object("config")
    if config:
        app.config.update(config)

    with app.app_context():
        init_db()

    app.register_blueprint(capture_bp)
    app.register_blueprint(search_bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True)
