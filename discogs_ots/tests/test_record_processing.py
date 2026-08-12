import pytest
import sys
import tempfile
import textwrap
import os
from dataclasses import dataclass
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
    assert cr.formats == ["CD [HDCD, Album]"]
    #assert cr.label == "E-Squared, Artemis Records"
    assert cr.labels ==  ["E-Squared", "Artemis Records"]
    assert cr.country == "US"
    assert cr.year == 2000
    assert cr.genres == ["Rock", "Folk, World, & Country"]
    assert cr.styles == ["Country Rock", "Country"]
    tl = cr.tracklist
    assert len(tl) == 15
    (title, track_pos), track_info = next(iter(tl.items()))
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
    assert cr.formats == ["LP [MP3, Album]"]
    assert cr.labels == ["First Label"]
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == ["Electronic", "Shoe Gaze"]
    assert cr.styles == ["Modern Classical", "Chipmonk", "Ambient"]

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == [] # no written by

    (title, track_pos), track_info = next(iter(tl.items()))
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == []
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    (title, track_pos), track_info = next(iterator)
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
    assert cr.formats == ["LP [Album]"]
    assert cr.labels == ["First Label", "Second Label"]
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == ["Acid Shoe Gaze"]
    assert cr.styles == ["Modern Classical"]

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy and not Some Other Guy"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    (title, track_pos), track_info = next(iterator)
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
    assert cr.formats == ["LP"]
    assert cr.labels == ["First Label", "Second Label"]
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == ["Acid Shoe Gaze"]
    assert cr.styles == ["Modern Classical"]

    assert cr.credits.get("Master Blaster", []) == ["Drums", "More Drums", "Even More Drums"]
    assert cr.credits.get("Tortued Artist", []) == []
    assert cr.credits.get("Smooth Player", []) == ["Tasty Licks"]

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy in the Master"
    assert track_info.written_by == ["John B Buoy"]
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == ["Tortured Artist"] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ["Evan Tully"]

    assert s.st.has_tl_only_in_record == 0
    assert s.st.has_tl_only_in_master == 1

# Top-level extra artists
def test_record_extraartists(monkeypatch, discogs_connection):

    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "15", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 15
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release with Extra Artists"
    assert cr.formats == ["LP [Album]", "Gramophone [Wax]"]
    assert cr.labels == ["First Label"]
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == ["Deep Vibe", "Shoe Gaze"]
    assert cr.styles == ["Trad Classical"]

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == ['Free Byrd'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusa"
    assert track_info.performed_by == "Tom I Aint, Tom I Am Not"
    assert track_info.written_by == ['Free Byrd'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['Song Writer Jr.'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == ['Free Byrd'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == ['Free Byrd'] 

    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ['Free Byrd'] 

    assert s.csv_rows[15].strip() == '15,Porch Chops & Tom J,Release with Extra Artists,LP [Album]|Gramophone [Wax],First Label,UK,2005,Deep Vibe|Shoe Gaze,Trad Classical,"Title 1++Performed by Some Guy++Written by Free Byrd|Scusa++Performed by Tom I Aint, Tom I Am Not++Written by Free Byrd|Title with, comma++Performed by Porch Chops & Tom J++Written by Song Writer Jr.|We\'re Number 4++Performed by Winken, Blinken, and Nod++Written by Free Byrd|Penultimate Tune++Performed by Unknown++Written by Free Byrd|Finally, ""right?""++Performed by Anonymous++Written by Free Byrd",I P Freely[Guitar]|John Dough[Engineer]'

    assert s.st.has_ea_only_in_record == 1
    assert s.st.has_tl_only_in_record == 1
    assert s.st.has_tl_only_in_master == 0

# Top-level written-by with specific tracks
def test_record_extraartists_with_tracks(monkeypatch, discogs_connection):

    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "16", "-ua", "testus", "-ir", "Engineer, Gofer" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 16
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release with Extra Artists"
    assert cr.formats == ["LP [Album]", "Gramophone [Wax]"]
    assert cr.labels == ["First Label"]
    assert cr.country == "UK"
    assert cr.year == 2015
    assert cr.genres == ["Deep Vibe", "Shoe Gaze"]
    assert cr.styles == ["Trad Classical"]
    assert cr.credits.get("I P Freely", []) == ["Guitar"]
    assert cr.credits.get("John Dough", []) == ["Kazoo"]
    assert cr.credits.get("The Third Man", []) == ["Zither", "Viola"]
    assert cr.credits.get("Just an Engineer", []) == []
    assert cr.credits.get("Not Just a Gofer", []) == ["Harp"]
    assert cr.credits.get("Free Byrd", []) == []

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == ['Writer of A1 and A4'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusa"
    assert track_info.performed_by == "Tom I Aint, Tom I Am Not"
    assert track_info.written_by == ['Free Byrd'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['Song Writer Jr.'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == ['Writer of A1 and A4', 'Co-Writer of A4'] 
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == ['Writer of A5-A6'] 

    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ['Writer of A5-A6'] 

    assert s.st.has_ea_only_in_record == 1
    assert s.st.has_tl_only_in_record == 1
    assert s.st.has_tl_only_in_master == 0

def test_main_release_has_extraartists(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cmr", "-id", "17", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 17
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release + Main Release, No Extra Artists in Release"
    assert cr.formats == ["LP"]
    assert cr.labels == ["First Label", "Second Label"]
    assert cr.country == "Cameroon"
    assert cr.year == 2005
    assert cr.genres == ["Acid Shoe Gaze"]
    assert cr.styles == ["Modern Classical"]
    assert cr.credits.get("Sam I Am", []) == ["Guitar"]
    assert cr.credits.get("John Boy", []) == ["Engineer"]
    assert cr.credits.get("Larry Byrd", []) == []
    assert cr.credits.get("I Wroteaverse", []) == []

    tl = cr.tracklist
    assert len(tl) == 8
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "A Clown with a Kazoo"
    assert track_info.written_by == ['Larry Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusa"
    assert track_info.performed_by == "Tom I Aint & Tom I Am Not"
    assert track_info.written_by == ['Larry Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['I Wroteaverse']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == ['Larry Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == ['Larry Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, right?"
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ['Larry Free Byrd']

    (title, track_pos), track_info = next(iterator)
    assert title == "Bonus Tracks-First Bonus"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['Larry Free Byrd']

    (title, track_pos), track_info = next(iterator)
    assert title == "Bonus Tracks-Second Bonus"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['I Wroteaverse']

    assert s.st.has_ea_only_in_main_release == 1

def test_per_track_extraartists(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cmr", "-id", "19", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 19
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release with Per Track Extra Artists"
    assert cr.formats == ["LP [Album]", "Gramophone [Wax]"]
    assert cr.labels == ["First Label"]
    assert cr.country == "Canada"
    assert cr.year == 2026
    assert cr.genres == ["Deep Vibe", "Shoe Gaze"]
    assert cr.styles == []
    assert cr.credits.get("I P Freely", []) == ["Guitar", "Bass Guitar", "Pedal Steel", "Washboard", "Organ"]
    assert cr.credits.get("John Marching", []) == ["Spoons"]
    assert cr.credits.get("John John", []) == []
    assert cr.credits.get("Larry Byrd", []) == []
    assert cr.credits.get("I Wroteaverse", []) == []

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy"
    assert track_info.written_by == ['John Buoy']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusa"
    assert track_info.performed_by == "Tom I Aint & Tom I Am Not"
    assert track_info.written_by == ['John John']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == ['Song Writer Jr.']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "We're Number 4"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == ['Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == ['Free Byrd']
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == ['Free Byrd']

    assert s.st.has_ea_only_in_record == 1
    assert s.st.has_ea_only_in_main_release == 0

# Some compilations albums have duplicate track names which need to be
# treated separately
def test_duplicate_track_names(monkeypatch, discogs_connection):

    # No extra artists
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-id", "20", "-ua", "testus" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    s.run()
    cr = s.current_record
    assert cr.id == 20
    assert cr.artists == "Porch Chops & Tom J"
    assert cr.title == "Release + Master, No Extra Artists"
    assert cr.formats == ["LP [Album]"]
    assert cr.labels == ["First Label", "Second Label"]
    assert cr.country == "UK"
    assert cr.year == 2005
    assert cr.genres == ["Acid Shoe Gaze"]
    assert cr.styles == ["Modern Classical"]

    tl = cr.tracklist
    assert len(tl) == 6
    iterator = iter(tl.items())
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Some Guy and not Some Other Guy"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Scusi"
    assert track_info.performed_by == "Tom I Am & Tom I Am Not"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title with, comma"
    assert track_info.performed_by == "Porch Chops & Tom J"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Title 1"
    assert track_info.performed_by == "Winken, Blinken, and Nod"
    assert track_info.written_by == [] # no written by
    
    (title, track_pos), track_info = next(iterator)
    assert title == "Penultimate Tune"
    assert track_info.performed_by == "Unknown"
    assert track_info.written_by == [] # no written by

    (title, track_pos), track_info = next(iterator)
    assert title == "Finally, \"right?\""
    assert track_info.performed_by == "Anonymous"
    assert track_info.written_by == [] # no written by

    assert s.st.has_tl_only_in_record == 1

def test_record_list(monkeypatch, discogs_connection):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False) as temp_file:
        try:
            temp_file.write("14\n15")
            temp_file.close() # Ensure data is written to disk
            monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-i", f"{temp_file.name}", "-ua", "testus" ])
            d = discogs_connection
            s = OtsDiscogsToCsv(d)
            s.run()
            assert 14 in s.csv_rows
            assert 15 in s.csv_rows
            assert 16 not in s.csv_rows
        finally:
            os.remove(temp_file.name)

    # Same test with cfg file
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False) as temp_file, tempfile.NamedTemporaryFile(mode='w+t', suffix='.cfg', delete=False) as cfg_file:
        try:
            cfg = textwrap.dedent(f"""
                [api]
                user_token = 
                user_agent = userage

                [settings]
                input_file = {temp_file.name}
            """)

            cfg_file.write(cfg)
            cfg_file.close() # Ensure data is written to disk

            temp_file.write("14\n16")
            temp_file.close() # Ensure data is written to disk

            monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-i", f"{temp_file.name}", "-c", f"{cfg_file.name}"])
            d = discogs_connection
            s = OtsDiscogsToCsv(d)
            s.run()
            assert 14 in s.csv_rows
            assert 15 not in s.csv_rows
            assert 16 in s.csv_rows
        finally:
            os.remove(temp_file.name)
            os.remove(cfg_file.name)

# If the input file is a (previously generated) csv, make sure extra data is ignored (only extract record ids)
def test_record_list_from_csv(monkeypatch, discogs_connection):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False) as temp_file:
        try:
            temp_file.write("record_id,\ntitle\n")
            temp_file.write('14,"This is a title"\n')
            temp_file.write('15 "This is another title with whitespace separator"\n')
            temp_file.close() # Ensure data is written to disk
            monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-i", f"{temp_file.name}", "-ua", "testus" ])
            d = discogs_connection
            s = OtsDiscogsToCsv(d)
            s.run()
            assert 14 in s.csv_rows
            assert 15 in s.csv_rows
            assert 16 not in s.csv_rows
        finally:
            os.remove(temp_file.name)

@dataclass
class MockRelease:
    id: int

def test_record_query(monkeypatch, discogs_connection):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-qi", "-ua", "testus", "-ut", "1234567890" ])
    d = discogs_connection
    s = OtsDiscogsToCsv(d)
    my_releases = [
            MockRelease(15),
            MockRelease(16),
            ]

    s.my_releases=my_releases
    s.run()
    assert 14 not in s.csv_rows
    assert 15 in s.csv_rows
    assert 16 in s.csv_rows

def test_new_records_only(monkeypatch, discogs_connection):
    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False) as input_file:
        try:
            input_file.write("14\n15")
            input_file.close() # Ensure data is written to disk
            monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-nro", "-qi", "-i", f"{input_file.name}", "-ua", "testus", "--user-token", "1334343" ])
            d = discogs_connection
            s = OtsDiscogsToCsv(d)

            my_releases = [
                MockRelease(14),
                MockRelease(15),
                MockRelease(16),
            ]
            s.my_releases=my_releases

            s.run()
            assert 14 not in s.csv_rows
            assert 15 not in s.csv_rows
            assert 16 in s.csv_rows
        finally:
            os.remove(input_file.name)

    with tempfile.NamedTemporaryFile(mode='w+t', suffix='.txt', delete=False) as input_file:
        try:
            input_file.write("14")
            input_file.close() # Ensure data is written to disk
            monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-cm", "-nro", "-qi", "-i", f"{input_file.name}", "-ua", "testus", "--user-token", "1334343" ])
            d = discogs_connection
            s = OtsDiscogsToCsv(d)

            my_releases = [
                MockRelease(14),
                MockRelease(15),
                MockRelease(16),
            ]
            s.my_releases=my_releases

            s.run()
            assert 14 not in s.csv_rows
            assert 15 in s.csv_rows
            assert 16 in s.csv_rows
        finally:
            os.remove(input_file.name)





