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
    assert cr.formats == "CD [HDCD, Album]"
    #assert cr.label == "E-Squared, Artemis Records"
    assert cr.labels ==  "E-Squared [751033-2] | Artemis Records [751033-2]"
    assert cr.country == "US"
    assert cr.year == 2000
    assert cr.genres == "Rock | Folk, World, & Country"
    assert cr.styles == "Country Rock | Country"
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
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "No Extra Artists"
    assert cr.formats == "LP [MP3, Album]"
    assert cr.labels == "First Label [CAT-1]"
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == "Electronic | Shoe Gaze"
    assert cr.styles == "Modern Classical | Chipmonk | Ambient"

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    track = next(iterator)
    assert track[0] == "Title 1"
    assert track[1][0] == "Some Guy"
    assert track[1][1] == [] # no written by
    
    track = next(iterator)
    assert track[0] == "Scusi"
    assert track[1][0] == "Tom I Am & Tom I Am Not"
    assert track[1][1] == [] # no written by
    
    track = next(iterator)
    assert track[0] == "Title with, comma"
    assert track[1][0] == "Porch Chops & Tom J"
    assert track[1][1] == [] # no written by
    
    track = next(iterator)
    assert track[0] == "We're Number 4"
    assert track[1][0] == "Winken, Blinken, and Nod"
    assert track[1][1] == [] # no written by
    
    track = next(iterator)
    assert track[0] == "Penultimate Tune"
    assert track[1][0] == "Unknown"
    assert track[1][1] == [] # no written by

    track = next(iterator)
    assert track[0] == "Finally, \"right?\""
    assert track[1][0] == "Anonymous"
    assert track[1][1] == [] # no written by

    assert s.st.has_tl_only_in_record == 1


