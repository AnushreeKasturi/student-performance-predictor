import logging
import secrets

from flask import Flask, render_template

from .config import BASE_DIR, Config
from .extensions import csrf, db, login_manager

log = logging.getLogger(__name__)


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_path=str(BASE_DIR / "instance"))
    app.config.from_object(config)

    if not app.config.get("SECRET_KEY"):
        # Fine for local development; set SECRET_KEY in production so
        # sessions survive restarts and work across multiple workers.
        log.warning("SECRET_KEY is not set; using a random key for this process.")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        (BASE_DIR / "instance").mkdir(exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import api, auth, classroom, dashboard, demo

    app.register_blueprint(auth.bp)
    app.register_blueprint(demo.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(classroom.bp)
    app.register_blueprint(api.bp)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("error.html", code=403,
                               message="This page is only available to teacher accounts."), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", code=404, message="Page not found."), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template("error.html", code=500, message="Something went wrong."), 500

    with app.app_context():
        db.create_all()

    return app
