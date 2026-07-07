import pytest
import sys
import os
from discogs_ots import OtsDiscogsToCsv
from discogs_client import Client
from discogs_client.fetchers import LoggingDelegator, FilesystemFetcher

@pytest.fixture(scope="class")
def discogs_connection():
    # Filesystem client
    d = Client('test_client/0.1 +http://example.org')
    d._base_url = ''
    d._fetcher = LoggingDelegator(
            FilesystemFetcher(os.path.dirname(os.path.abspath(__file__)) + '/res')
        )
    d._verbose = True
    return d

def test_discogs_connection(monkeypatch):
    
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])

    d = discogs_connection
    s = OtsDiscogsToCsv()

