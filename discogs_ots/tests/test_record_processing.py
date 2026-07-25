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
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "12345", "-ua", "testus"])
    d = discogs_connection
    #r =  d.release(1799382)
    #print(r)
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 12345
    assert cr.artists == "Steve Earle"
    assert cr.title == "Transcendental Blues"
    assert cr.format == "CD"
    assert cr.format_descriptions == "HDCD, Album"
    #assert cr.label == "E-Squared, Artemis Records"
    assert cr.label == "E-Squared"
    assert cr.cat_no == "751033-2"
    assert cr.country == "US"
    assert cr.year == 2000
    assert cr.genres == "Rock, Folk, World, & Country"
    assert cr.styles == "Country Rock, Country"
    tl = cr.tracklist
    assert len(tl) == 15
    t1 = next(iter(tl.items()))
    assert t1[0] == "Transcendental Blues"
    assert t1[1][0] == "Steve Earle"
    assert t1[1][1] == ["Steve Earle"]

    assert cr.album_written_by == ["Steve Earle"]

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "12", "-ua", "testus"])
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 12
    assert cr.artists == "Trash80 & Dma-Sc"


