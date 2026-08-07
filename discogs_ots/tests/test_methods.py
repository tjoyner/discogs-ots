import pytest
import re
import sys
from discogs_ots import OtsDiscogsToCsv
from discogs_ots import TrackInfo

# remove for now, not needed?
def dont_test_sort(monkeypatch):
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

def test_ignore_role(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus", "--ignore-roles", 'rolea, role b'])
    s = OtsDiscogsToCsv()
    assert s.ignore_role("rolec") is False
    assert s.ignore_role("rolea")
    assert s.ignore_role("role") is False
    assert s.ignore_role("role b")
    assert s.ignore_role("role b plus") # ignore role is contained in role

def test_written_by_in_role(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])
    s = OtsDiscogsToCsv()
    assert s.is_written_by_in_role('not in here') is False
    assert s.is_written_by_in_role('Written By')
    assert s.is_written_by_in_role('written-By')
    assert s.is_written_by_in_role('composed by')
    assert s.is_written_by_in_role('composed-by')
    assert s.is_written_by_in_role('is composed-by')
    assert s.is_written_by_in_role('is written-by i think')
    assert s.is_written_by_in_role(' written by')

def test_split_roles(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])
    s = OtsDiscogsToCsv()
    assert s.split_roles("a, b[c, d]") == ["a", "b[c, d]"]
    assert s.split_roles("a, b") == ["a", "b"]
    assert s.split_roles("a, b, cdefg") == ["a", "b", "cdefg"]
    assert s.split_roles("a, b[this is a longer list, with a comma], cdefg") == ["a", "b[this is a longer list, with a comma]", "cdefg"]

    assert s.split_roles("Photography By [Pages 11, 12]") == ["Photography By [Pages 11, 12]"]

def test_expand_track_positions(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])
    s = OtsDiscogsToCsv()
    track_list = {
            'track 1' : TrackInfo(position='a1'),
            'track 2' : TrackInfo(position='a2'),
            'track 3' : TrackInfo(position='b1'),
            'track 4' : TrackInfo(position='b2'),
            'track 5' : TrackInfo(position='b3'),
            'track 6' : TrackInfo(position='6')
            }
    track_positions = [t.position for t in track_list.values()]
    assert s.expand_tracks("a1, a2", track_positions) == (["a1", "a2"], False)
    assert s.expand_tracks("a1; a2", track_positions) == (["a1", "a2"], False)
    assert s.expand_tracks("a1 to a2", track_positions) == (["a1", "a2"], True)
    assert s.expand_tracks("a1 to b1", track_positions) == (["a1", "a2", "b1"], True)
    assert s.expand_tracks("a1 - b2", track_positions) == (["a1", "a2", "b1", "b2"], True)
    assert s.expand_tracks("a1-a2", track_positions) == (["a1", "a2"], True)
    assert s.expand_tracks("b2 to 6", track_positions) == (["b2", "b3", "6"], True)
    assert s.expand_tracks("b2 to b2", track_positions) == (["b2"], True)

    assert s.expand_tracks("A5 to A6", ["A1", "A2", "A3", "A4", "A5", "A6"]) == (["A5", "A6"], True)
    # Some invalid cases
    assert s.expand_tracks("b2 to 7", track_positions) == ([], True)
    assert s.expand_tracks("a2 to a1", track_positions) == ([], True)
    assert s.expand_tracks("b1 to a2", track_positions) == ([], True)
    assert s.expand_tracks("1 to 6", track_positions) == ([], True)
    assert s.expand_tracks("C1", track_positions) == ([], False)

    # track positions contain dash
    track_positions = ["1-1", "1-2", "1-3", "2-1"]
    assert s.expand_tracks("1-1, 1-2", track_positions) == (["1-1", "1-2"], False)
    assert s.expand_tracks("1-1 to 1-3", track_positions) == (["1-1", "1-2", "1-3"], True)

def test_fix_year(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus", "--ignore-roles", 'rolea, role b'])
    s = OtsDiscogsToCsv()
    assert s.fix_year("2016") == 2016
    assert s.fix_year("2016.0") == 2016
    assert s.fix_year("") == 0
    assert s.fix_year("0") == 0
    assert s.fix_year("0.0") == 0
    assert s.fix_year("not") == 0
