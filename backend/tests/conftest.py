import os
import pytest
from unittest.mock import MagicMock
from db import Database

# Set required env vars before any module that imports config is loaded
os.environ.setdefault('GOOGLE_CLIENT_ID', 'test-client-id')
os.environ.setdefault('GOOGLE_CLIENT_SECRET', 'test-client-secret')


@pytest.fixture
def db(tmp_path):
    """In-memory SQLite database for each test."""
    database = Database(str(tmp_path / 'test.db'))
    yield database
    database.close()


@pytest.fixture
def mock_creds():
    """Fake Credentials object — never makes real network calls."""
    creds = MagicMock()
    creds.valid = True
    creds.expired = False
    creds.refresh_token = 'fake-refresh-token'
    return creds


@pytest.fixture
def mock_gmail_service():
    """Mock Google API service object."""
    return MagicMock()
