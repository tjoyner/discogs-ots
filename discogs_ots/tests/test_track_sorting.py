import pytest
import sys
from discogs_ots import OtsDiscogsToCsv

def test_sort(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])

    s = OtsDiscogsToCsv()
    assert s.sort_track_pos(("A3", '')) == ("A", "00003")
    assert s.sort_track_pos(("3", '')) == ("", "00003")
    assert s.sort_track_pos(("30", '')) == ("", "00030")
    assert s.sort_track_pos(("1-1", '')) == ("00001", "00001")
    assert s.sort_track_pos(("10-1", '')) == ("00010", "00001")
    mixed = {
            '1-2' : ('a', []), 
            '1-1' : ('a', []), 
            '3-2' : ('a', []), 
            '1-3' : ('a', []), 
            '3-26' : ('a', []), 
            'd3' : ('a', []),
            'A5' : ('a', []),
            '1' : ('a', []),
            'C' : ('a', []),
            '3-7' : ('a', []) 
    }
    mixed_expected = [
            ('1' , ('a', [])),
            ('1-1' , ('a', [])),
            ('1-2' , ('a', [])),
            ('1-3' , ('a', [])),
            ('3-2' , ('a', [])),
            ('3-7' , ('a', [])),
            ('3-26' , ('a', [])),
            ('A5' , ('a', [])),
            ('C' , ('a', [])),
            ('d3' , ('a', []))
            ]
    mixed_actual = sorted(mixed.items(), key=s.sort_track_pos)
    assert mixed_actual == mixed_expected

def test_fix_artist(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])
    s = OtsDiscogsToCsv()
    assert s.fix_artist_name("Joe Guitar") == "Joe Guitar"
    assert s.fix_artist_name("Joe Guitar(1)") == "Joe Guitar"
    assert s.fix_artist_name("Joe Guitar (2)") == "Joe Guitar"
    assert s.fix_artist_name("Joe Guitar  (3)") == "Joe Guitar"
    assert s.fix_artist_name("Joe Guitar  (4) ") == "Joe Guitar"
