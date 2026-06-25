"""Shared pytest fixtures.

The Flask app object lives in ``app.py`` as the module-level ``app``. Here we
expose it in *testing* mode and provide a Werkzeug test client so route tests
can issue requests without a running server or any network access.
"""

import pytest

import app as flask_app_module


@pytest.fixture()
def app():
    """The Flask application configured for testing."""
    flask_app_module.app.config.update(TESTING=True)
    return flask_app_module.app


@pytest.fixture()
def client(app):
    """A test client for issuing requests against the app in-process."""
    return app.test_client()
