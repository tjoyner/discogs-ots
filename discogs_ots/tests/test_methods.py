import pytest
import re
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
