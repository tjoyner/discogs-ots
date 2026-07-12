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
    print (os.path.dirname(os.path.abspath(__file__)) + '/res')
    yield d

def test_load_release(monkeypatch, discogs_connection):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "1799382", "-ua", "testus"])
    d = discogs_connection
    #r =  d.release(1799382)
    #print(r)
    s = OtsDiscogsToCsv(d)
    s.run()

