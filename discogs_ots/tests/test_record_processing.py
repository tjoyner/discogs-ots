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
    assert cr.labels ==  "E-Squared [751033-2]|Artemis Records [751033-2]"
    assert cr.country == "US"
    assert cr.year == 2000
    assert cr.genres == "Rock|Folk, World, & Country"
    assert cr.styles == "Country Rock|Country"
    tl = cr.tracklist
    assert len(tl) == 15
    title, track_info = next(iter(tl.items()))
    assert title == "Transcendental Blues"
    assert track_info.performed_by == "Steve Earle"
    assert track_info.written_by == ["Steve Earle"]

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
    assert cr.genres == "Electronic|Shoe Gaze"
    assert cr.styles == "Modern Classical|Chipmonk|Ambient"

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    title, track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == [] # no written by

    title, track_info = next(iter(tl.items()))
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == []
    
    title, track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    title, track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == [] # no written by

    assert s.st.has_tl_only_in_record == 1

# check master is set, but tracklist was found in record
def test_load_release_with_check_master(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "13", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 13
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release + Master, No Extra Artists"
    assert cr.formats == "LP [Album]"
    assert cr.labels == "First Label [CAT-1]|Second Label [CAT-2]"
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == "Acid Shoe Gaze"
    assert cr.styles == "Modern Classical"

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    title, track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy and not Some Other Guy"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    title, track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == [] # no written by

    assert s.st.has_tl_only_in_record == 1

def test_load_release_with_master_tracklist(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "14", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 14
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release + Master, No Track List"
    assert cr.formats == "LP"
    assert cr.labels == "First Label [CAT-1]|Second Label [CAT-2]"
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == "Acid Shoe Gaze"
    assert cr.styles == "Modern Classical"

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    title, track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy in the Master"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    title, track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    title, track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == [] # no written by

    assert s.st.has_tl_only_in_record == 0
    assert s.st.has_tl_only_in_master == 1

# Top-level extra artists
def test_record_extraartists(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "15", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 15
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release with Extra Artists"
    assert cr.formats == "LP [Album]|Gramophone [Wax]"
    assert cr.labels == "First Label [CAT-1]"
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == "Deep Vibe|Shoe Gaze"
    assert cr.styles == "Trad Classical"

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    title, track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == ['Free Byrd'] 
    
    title, track_info = next(iterator)
    assert title == "Scusa"
    assert track_info.performed_by == "Tom I Aint, Tom I Am Not"
    assert track_info.written_by == ['Free Byrd'] 
    
    title, track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['Free Byrd'] 
    
    title, track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == ['Free Byrd'] 
    
    title, track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == ['Free Byrd'] 

    title, track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ['Free Byrd'] 

    assert s.st.has_ea_only_in_record == 1
    assert s.st.has_tl_only_in_record == 1
    assert s.st.has_tl_only_in_master == 0





