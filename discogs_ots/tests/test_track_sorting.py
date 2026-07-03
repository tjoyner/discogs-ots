import pytest
import sys
from discogs_ots import OtsDiscogsToCsv

def test_sort(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["discogs_ots.py", "-id", "11111", "-ua", "testus"])

    s = OtsDiscogsToCsv()
    assert s.sort_track_pos(("A3", '')) == ("A", 3)
    assert s.sort_track_pos(("3", '')) == ("", 3)
    assert s.sort_track_pos(("30", '')) == ("", 30)
    assert s.sort_track_pos(("1-1", '')) == (1, 1)
    assert s.sort_track_pos(("10-1", '')) == (10, 1)
