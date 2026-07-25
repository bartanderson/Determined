from flask import Flask
from config import Config
from storage.db import init_db
from routes.capture import capture_bp
from routes.browse import browse_bp
from routes.search import search_bp
from routes.api import api_bp


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    init_db(app)

    app.register_blueprint(capture_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
