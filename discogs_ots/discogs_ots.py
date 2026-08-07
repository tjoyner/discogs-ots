import discogs_client
from discogs_client.exceptions import HTTPError
import csv
from pathlib import Path
import time
import argparse
import sys
import os
import io
import re
import contextlib
import datetime
from dataclasses import dataclass, field
import pprint
import configparser
import json
import traceback
from collections import Counter

# temp fix for encoding: $env:PYTHONIOENCODING="utf-8"
#                        or set pythonencoding="utf-8"
# or: python your_script.py | Out-File -Encoding utf8 output.txt
API_ROLE = "role"
API_WRITTEN_BY = "Written-By"
API_WRITTEN_BY_NO_DASH = "Written By"
API_COMPOSED_BY = "Composed-By"
API_COMPOSED_BY_NO_DASH = "Composed By"
API_POSITION = "position"
API_EXTRAARTISTS = "extraartists"
API_TYPE_ = "type_"
API_TITLE = "title"
API_NAME = "name"
API_TRACKS = "tracks"
API_TRACKLIST = "tracklist"
API_TRACK_TYPE_TRACK = "track"
API_TRACK_TYPE_INDEX = "index"
API_TRACK_SUB_TRACKS = "sub_tracks"
API_ARTISTS = "artists"
API_JOIN = "join"
API_CATNO = "catno"
API_QTY = "qty"
API_DESCRIPTIONS = "descriptions"

CSV_RELEASE_ID="release_id"
CSV_ARTIST="artist"
CSV_TITLE="title"
CSV_FORMATS="formats"
CSV_LABELS="labels"
CSV_COUNTRY="country"
CSV_YEAR="year"
CSV_GENRES="genres"
CSV_STYLES="styles"
CSV_TRACKLIST="tracklist"
CSV_CREDITS="credits"

CSV_COL_SEPARATOR=","
CSV_ITEM_SEPARATOR1="|"
CSV_ITEM_SEPARATOR2="++"

headers = {
   CSV_RELEASE_ID : '',
   CSV_ARTIST : '',
   CSV_TITLE : '',
   CSV_FORMATS : '',
   CSV_LABELS : '',
   CSV_COUNTRY : '',
   CSV_YEAR : '',
   CSV_GENRES : '',
   CSV_STYLES : '',
   #"barcode" : 
   CSV_TRACKLIST : {},
   CSV_CREDITS : ''
   }

CFG_SETTINGS="settings"
CFG_API="api"

CFG_RECORD_ID="record_id"
CFG_INPUT_FILE="input_file"
CFG_OUTPUT_FILE="output_file"
CFG_LOG_FILE="log_file"
CFG_QUERY_FOR_IDS="query_for_ids"
CFG_IGNORE_ROLES="ignore_roles"
CFG_USER_AGENT="user_agent"
CFG_USER_TOKEN="user_token"
CFG_LOG_ALL_ROLES="log_all_roles"
CFG_NEW_RECORDS_ONLY="new_records_only"
CFG_CHECK_MASTER="check_master"

""" 
Read the artist and role into a list of tuples. 
Initially, convert to a cvs column. Generate 7 column csv file:
    - record id, title, master id, ea (record), ea per song (record), ea (master), ea per song (master)
    - Later, get track list
Left off (6/23/26: Roles can be overall or per/track, for instance, an artist can be a producer and also play
     on certain tracks)
Each record has 4 extra artist lists (for now)
    Each list is a dictionary with the artist name as a key, with a dictionary of roles
    Each role has a dictionary of tracks, which may be empty
"""

@dataclass
class TrackInfo:
    position: str = ''
    performed_by: str = ''
    written_by:  list = field(default_factory=list) 

@dataclass
class RecordInfo:
    id: int = 0

    artists: str = ''

    title: str = ''

    formats: str = ''

    labels: str = ''

    country: str = ''
    year: str = ''

    genres: str = ''
    styles: str = ''

    tracklist:  dict = field(default_factory=dict) # name : TrackInfo

    credits: dict = field(default_factory=dict)

    master_id: int = 0

    album_written_by:  list = field(default_factory=list) 

    # if an album level extra artist contains a written by with
    # a tracks element (so only particular tracks are written by
    # that artist), store the artist : tracks here so it
    # can be checked with the track list is processed
    album_written_by_tracks:  dict = field(default_factory=dict) 

@dataclass
class RecordStats:
    ea_found_in_record = False
    ea_found_in_master = False
    ea_found_in_main_release = False

    tl_found_in_record = False
    tl_found_in_master = False
    tl_found_in_main_release = False

    tl_ea_found_in_record = False
    tl_ea_found_in_master = False
    tl_ea_found_in_main_release = False

@dataclass
class AllStats:
    has_ea_only_in_record = 0
    has_ea_only_in_master = 0
    has_ea_only_in_main_release = 0
    has_ea_in_record_and_master = 0
    no_ea = 0

    has_tl_only_in_record = 0
    has_tl_only_in_master = 0
    has_tl_only_in_main_release = 0
    has_tl_in_record_and_master = 0
    no_tl = 0

    has_tl_ea_only_in_record = 0
    has_tl_ea_only_in_master = 0
    has_tl_ea_only_in_main_release = 0
    has_tl_ea_in_record_and_master = 0
    no_tl_ea = 0

    records = 0


class OtsDiscogsToCsv:
    # test cases will pass a test client
    def __init__(self, discogs_test_client=None):
        self.requests=0
        self.record_id = 0
        self.d = None

        # Use for testing
        self.test_case = False
        self.my_releases = None

        # dict record id : csv row
        self.csv_rows = {}


        if discogs_test_client:
            self.d = discogs_test_client
            self.test_case = True

        self.current_record = None

        self.start = datetime.datetime.now()

        self.ignore_roles = []

        self.all_roles = []

        args = self.parse_arguments()
        config = None
        if args.config:
            if not os.path.exists(args.config):
                print(f'Error: {args.config} does not exist')
                sys.exit(1)

            config = configparser.ConfigParser()
            config.read(args.config)

        output_file = None
        if args.output_file:
            output_file = args.output_file
        elif config and config.has_option(CFG_SETTINGS,CFG_OUTPUT_FILE):
            output_file = config[CFG_SETTINGS][CFG_OUTPUT_FILE]

        self.input_file = None
        if args.input_file:
            self.input_file = args.input_file
        if config and config.has_option(CFG_SETTINGS,CFG_INPUT_FILE):
            self.input_file = config[CFG_SETTINGS][CFG_INPUT_FILE]

        if args.record_id:
            self.record_id = args.record_id
        elif config and config.has_option(CFG_SETTINGS,CFG_OUTPUT_FILE):
            self.record_id = config[CFG_SETTINGS][CFG_RECORD_ID]

        log_file = None
        if args.log_file:
            log_file = args.log_file
        elif config and config.has_option(CFG_SETTINGS,CFG_LOG_FILE):
            log_file = config[CFG_SETTINGS][CFG_LOG_FILE]

        self.user_agent = None
        if args.user_agent:
            self.user_agent = args.user_agent
        elif config and config.has_option(CFG_API,CFG_USER_AGENT):
            self.user_agent = config[CFG_API][CFG_USER_AGENT]

        self.user_token = None
        if args.user_token:
            self.user_token = args.user_token
        elif config and config.has_option(CFG_API,CFG_USER_TOKEN):
            self.user_token = config[CFG_API][CFG_USER_TOKEN]

        self.query_for_ids = False
        if args.query_for_ids:
            self.query_for_ids = True
        elif config and config.has_option(CFG_SETTINGS,CFG_QUERY_FOR_IDS):
            self.query_for_ids = config[CFG_SETTINGS][CFG_QUERY_FOR_IDS]

        ignore_roles = None
        if args.ignore_roles:
            ignore_roles = args.ignore_roles.strip()
        elif config and config.has_option(CFG_SETTINGS,CFG_IGNORE_ROLES):
            ignore_roles = config[CFG_SETTINGS][CFG_IGNORE_ROLES].strip()

        self.log_all_roles = False
        if args.log_all_roles:
            self.log_all_roles = True
        elif config and config.has_option(CFG_SETTINGS,CFG_LOG_ALL_ROLES):
            self.log_all_roles = config[CFG_SETTINGS][CFG_LOG_ALL_ROLES]

        self.new_records_only = False
        if args.new_records_only:
            self.new_records_only = True
        elif config and config.has_option(CFG_SETTINGS,CFG_NEW_RECORDS_ONLY):
            self.new_records_only = config[CFG_SETTINGS][CFG_NEW_RECORDS_ONLY]

        self.check_master = False
        if args.check_master:
            self.check_master = True
        elif config and config.has_option(CFG_SETTINGS,CFG_CHECK_MASTER):
            self.check_master = config[CFG_SETTINGS][CFG_CHECK_MASTER]

        if ignore_roles:
            for r in ignore_roles.split(','):
                rs = r.strip()
                if rs:
                    self.ignore_roles.append(rs)

        self.out = None
        if output_file:
            try:
                self.out = open(output_file, mode='x', encoding='utf-8')
            except FileExistsError:
                print (f'{output_file} already exists')
                sys.exit(1)
        else:
            sys.stdout.reconfigure(encoding='utf-8') # Keep PowerShell happy!
            self.out = sys.stdout

        self.log_out = None
        if log_file:
            try:
                self.log_out = open(log_file, mode='x', encoding='utf-8')
            except FileExistsError:
                print (f'{log_file} already exists')
                sys.exit(1)
        elif output_file:
            log_file = Path(output_file).with_suffix('.log')
            try:
                self.log_out = open(log_file, mode='x', encoding='utf-8')
            except FileExistsError:
                print (f'{log_file} already exists')
                sys.exit(1)
        else:
            sys.stdout.reconfigure(encoding='utf-8') # Keep PowerShell happy!
            self.log_out = self.out

        if not self.user_agent:
            print ('user_agent must be specified')
            sys.exit(1)

        if not self.user_token and self.query_for_ids:
            print ("A user token is required for the query option")
            sys.exit(1)

        if self.new_records_only:
            if not self.query_for_ids or not self.input_file:
                print ("new-records-only also requires input-file and query-for-ids")
                sys.exit(1)
        else:
            entered = 0
            if self.query_for_ids:
                entered += 1 
            if self.input_file:
                entered += 1 
            if self.record_id:
                entered += 1 
            if entered > 1:
                print ("Only one of input-file, query-for-ids, or record-id can be entered")
                sys.exit(1)

            if not self.record_id and not self.query_for_ids and not self.input_file:
                print ("Enter input-file, query-for-ids or record-id")
                sys.exit(1)

    def run(self):
        if not self.d:
            self.d = discogs_client.Client(self.user_agent,user_token=self.user_token)

        self.init_csv()

        self.st = AllStats()

        if self.record_id:
            self.get_record_data(self.record_id)
            self.st.records = 1
            self.log_final_stats()
            return


        my_releases = []
        if self.query_for_ids:
            if self.test_case:
                my_releases = self.my_releases
            else:
                me = self.d.identity()
                my_releases = me.collection_folders[0].releases

            records_to_skip = [] 
            if self.new_records_only:
                with open(self.input_file, mode='r', newline='', encoding='utf-8') as file:
                    for row in file:
                        record_id_i = self.extract_record_id(row)
                        if record_id_i and record_id_i > 0:
                            records_to_skip.append(record_id_i)

            seen = {}
            duplicates = []
            for r in my_releases:
                if r.id in seen:
                    self.writelog(f'Skipping duplicate record ID {r.id}')
                    duplicates.append(r.id)
                    continue
                else:
                    seen[r.id] = None

                if r.id not in records_to_skip:
                    if self.get_record_data(r.id):
                        self.st.records += 1
        else:
            with open(self.input_file, mode='r', newline='', encoding='utf-8') as file:
                # Iterate through each row
                for row in file:
                    record_id_i = self.extract_record_id(row)
                    if record_id_i and record_id_i > 0:
                        if self.get_record_data(f'{record_id_i}'):
                            self.st.records += 1

        self.log_final_stats()

    # read ID from first position in file, ignore anything that comes after.
    def extract_record_id(self, row):
        record_id = None
        match = re.match(r"^\s*(\d+)", row)
        if match:
            record_id = int(match.group(1))
        return record_id

    def get_record_data(self, record_id):
        try:
            record_id_i = self.to_int(record_id)

            if record_id_i == 0:
                self.writelog(f'Skipping invalid record ID {record_id}')
                return False

            self.rs = RecordStats()

            self.release = self.d.release(record_id)
            self.release.refresh()

            self.requests += 1

            self.current_record = RecordInfo()
            self.current_record.id = record_id_i
            self.current_record.title = self.release.title
            self.master = False
            self.main_release = False

            self.store_record_data()

            # TODO: Only check master if no tracklist found?
            #       Need to remove the "both found" stats
            # TODO: read master per/track extra artist if not found
            if self.check_master and self.release.master and not self.rs.tl_found_in_record:
                masterRec = self.release.master
                master = None

                self.master = True
                master = self.d.master(masterRec.id)
                master.refresh()
                self.store_master_data(master)

            self.write_csv()

            #if master.main_release and master.main_release.id != record_id:
            #    self.main_release = True
            #    main_release = self.d.release(master.main_release.id)
            #    main_release.refresh()
            #    ea_found_in_main_release  = self.get_extraartists(main_release)

            if self.rs.ea_found_in_record and self.rs.ea_found_in_master:
                self.st.has_ea_in_record_and_master += 1
            elif self.rs.ea_found_in_record:
                self.st.has_ea_only_in_record += 1
            elif self.rs.ea_found_in_master:
                self.st.has_ea_only_in_master += 1
            elif not self.rs.ea_found_in_master and not self.rs.ea_found_in_record and self.rs.ea_found_in_main_release:
                self.st.has_ea_only_in_main_release += 1
            else:
                self.st.no_ea += 1

            if self.rs.tl_found_in_record and self.rs.tl_found_in_master:
                self.st.has_tl_in_record_and_master += 1
            elif self.rs.tl_found_in_record:
                self.st.has_tl_only_in_record += 1
            elif self.rs.tl_found_in_master:
                self.st.has_tl_only_in_master += 1
            elif not self.rs.tl_found_in_master and not self.rs.tl_found_in_record and self.rs.tl_found_in_main_release:
                self.st.rs.has_tl_only_in_main_release += 1
            else:
                self.st.no_tl += 1

            if self.rs.tl_ea_found_in_record and self.rs.tl_ea_found_in_master:
                self.st.has_tl_ea_in_record_and_master += 1
            elif self.rs.tl_ea_found_in_record:
                self.st.has_tl_ea_only_in_record += 1
            elif self.rs.tl_ea_found_in_master:
                self.st.has_tl_ea_only_in_master += 1
            elif not self.rs.tl_ea_found_in_master and not self.rs.tl_ea_found_in_record and self.rs.tl_ea_found_in_main_release:
                self.st.rs.has_tl_ea_only_in_main_release += 1
            else:
                self.st.no_tl_ea += 1

            return True
                

        except HTTPError as e:
            # Check if the error message or status inside the exception indicates a 404
            if e.status_code == 404:
                if self.master:
                    self.writelog(f"Master of record ID {record_id} was NOT found (404 Error).")
                    return False
                self.writelog(f"Record ID {record_id} was NOT found (404 Error).")
            else:
                self.writelog(f"A different API error occurred: {e}")
            return False

    def store_album_artists(self):
        artists = self.release.data.get(API_ARTISTS)
        if not artists:
            return
        self.current_record.artists = self.get_artists(artists) 

    def get_track_artists(self, track):
        artists = track.get(API_ARTISTS)
        if not artists:
            return self.current_record.artists
        return self.get_artists(artists) 

    def get_artists(self, artists) -> str:
        artist_names = ''
        join = ''
        for artist in artists:
            artist_name = self.fix_artist_name(artist.get(API_NAME))
            if not artist_name:
                self.writelog(f"Artist name was not specified in {artist}")
                return artist_names

            if artist_names:
                if join.startswith(','):
                    join = f'{join} '
                elif join:
                    join = f' {join} '
                artist_names = artist_names + join + artist_name
            else:
                artist_names = artist_name

            join = artist.get(API_JOIN, '').strip()
            if not join:
                join = ','

        return artist_names


    def store_formats(self):
        if not self.release.formats:
            return

        format_entries = []

        for format in self.release.formats:
            name = format.get(API_NAME, "").strip()
            qty = format.get(API_QTY, "1").strip()
            desc = ", ".join(format.get(API_DESCRIPTIONS) or [])
            if desc:
                desc = f' [{desc}]'
            #format_entries.append(f"{qty}x {name}{desc}")
            # FIXME: is qty needed?
            format_entries.append(f"{name}{desc}")

        self.current_record.formats = f"{CSV_ITEM_SEPARATOR1}".join(format_entries)

    def store_labels(self):
        if not self.release.labels:
            return

        label_entries = []

        for label in self.release.labels:
            name = label.name.strip()
            #name = label.get(API_NAME, "").strip()
            catno = label.catno.strip()
    
            # Format as "Label Name [Catalog Number]"
            if catno and catno.lower() != "none":
                label_entries.append(f"{name} [{catno}]")
            elif name:
                label_entries.append(name)

        self.current_record.labels = f"{CSV_ITEM_SEPARATOR1}".join(label_entries)

    def fix_artist_name(self, artist_name):
        if artist_name == None:
            return ''
        pattern = r"\s*\(\d+\)\s*$"
        return re.sub(pattern, '', artist_name)

    def is_written_by_in_role(self, role):
        if API_WRITTEN_BY.casefold() in role.casefold() or API_WRITTEN_BY_NO_DASH.casefold() in role.casefold():
            return True
        if API_COMPOSED_BY.casefold() in role.casefold() or API_COMPOSED_BY_NO_DASH.casefold() in role.casefold():
            return True
        return False

    def parse_arguments(self):
        """
        Handles command-line arguments for the Discogs script.
        """
        parser = argparse.ArgumentParser(
            description="Fetch record data from Discogs API and save to a file."
        )

        # Group for input options (Mutually exclusive means you must pick ONE)
        #input_group = parser.add_mutually_exclusive_group(required=True)
        
        parser.add_argument(
            '-i', '--input-file', 
            type=str, 
            help="Path to the input file containing a list of Discogs IDs."
        )
        
        parser.add_argument(
            '-id', '--record-id', 
            type=int, 
            help="A single Discogs Record/Release ID to process."
        )
        
        parser.add_argument(
            '-qi', '--query-for-ids', 
            action='store_true',
            help="Query discogs for the record_ids. user_token must be specified"
        )

        # Argument for the output file destination
        parser.add_argument(
            '-o', '--output-file', 
            type=str, 
            help="Path to the output text/CSV file where retrieved discogs information will be saved."
        )

        parser.add_argument(
            '-l', '--log-file', 
            type=str, 
            help="Path to the file where log messages will be saved. If not specified, the log file is 'output-file'.log"
        )
        
        parser.add_argument(
            '-c', '--config', 
            type=str, 
            help="Input configuration .ini file"
        )
        
        parser.add_argument(
            '-ua', '--user-agent', 
            type=str, 
            help="User-Agent to use for API request"
        )
        
        parser.add_argument(
            '-ut', '--user-token', 
            type=str, 
            help="User-Agent to use for authenticated API request"
        )

        parser.add_argument(
            '-ir', '--ignore-roles', 
            type=str, 
            help="A list of comma-separated roles to ignore"
        )

        parser.add_argument(
            '-lar', '--log-all-roles', 
            action='store_true', 
            help="Log all roles encountered, not including ignored roles."
        )

        parser.add_argument(
            '-nro', '--new-records-only', 
            action='store_true', 
            help="Only get records that aren't in the input list. Requires --query-for-ids and --input-file."
        )

        parser.add_argument(
            '-cm', '--check-master', 
            action='store_true', 
            help="Check the master record if one exists"
        )

        # Parse the arguments from the command line
        return parser.parse_args()

    def log_final_stats(self):
        if self.log_all_roles:
            self.log_all_roles_found()

        self.writelog(f'Total Records={self.st.records}\n')
        self.writelog(f'Extra Artists:\n    Found in record and master={self.st.has_ea_in_record_and_master}\n    Found in Record only={self.st.has_ea_only_in_record}  Master only={self.st.has_ea_only_in_master}\n    Not found={self.st.no_ea}\n    Main release only={self.st.has_ea_only_in_main_release}')
        self.writelog(f'Track lists:\n    Found in record and master={self.st.has_tl_in_record_and_master}\n    Found in Record only={self.st.has_tl_only_in_record} Master only={self.st.has_tl_only_in_master}\n    Not found={self.st.no_tl}\n    Main release only={self.st.has_tl_only_in_main_release}')
        self.writelog(f'Extra Artists in Track lists:\n    Found in record and master={self.st.has_tl_ea_in_record_and_master}\n    Found in Record only={self.st.has_tl_ea_only_in_record} Master only={self.st.has_tl_ea_only_in_master}\n    Not found={self.st.no_tl_ea}\n    Main release only={self.st.has_tl_ea_only_in_main_release}')
        time_difference = datetime.datetime.now() - self.start
        self.writelog(f'Total time: {time_difference}')

    def writeln(self, text=""):
        self.out.write(f"{text}\n")

    def writelog(self, text=""):
        id = self.current_record.id if self.current_record else ''
        padded_id = f"{id:>8}"
        self.log_out.write(f"{padded_id}: {text}\n")

    def log_all_roles_found(self):
        if not self.log_all_roles:
            return
        if self.all_roles:
            self.log_out.write("\nAll roles found:\n")
            self.all_roles.sort(key=str.lower)
            for r in self.all_roles:
                self.log_out.write(f"  {r}\n")
        else:
            self.log_out.write("\nNo roles found:\n")

        self.log_out.write('\n')

    def ignore_role(self, role):
        if not self.ignore_roles:
            return False
        for r in self.ignore_roles:
            if role.casefold().startswith(r.casefold()):
                return True
        return False

    def to_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def store_record_data(self) -> bool:
        try:
            self.store_album_artists()

            self.current_record.title = self.release.title

            self.store_formats()

            self.store_labels()

            self.current_record.country = self.release.country or ''

            year = self.release.year or ''

            self.current_record.year = self.fix_year(year)

            self.current_record.genres = f"{CSV_ITEM_SEPARATOR1}".join(self.release.genres or [])

            self.current_record.styles = f"{CSV_ITEM_SEPARATOR1}".join(self.release.styles or [])

            self.store_credits(self.release)

            self.store_tracklist(self.release)

            return True

        except Exception as e:
            self.writelog(f'Exception {e} occurred for {self.current_record}\n{traceback.format_exc()}')

        return False

    def fix_year(self, year) -> int:
        try:
            return int(float(year))
        except ValueError:
            return 0

    def store_master_data(self, master) -> bool:
        try:
            self.store_credits(master)

            self.store_tracklist(master)

            return True

        except Exception as e:
            self.writelog(f'Exception {e} occurred for {self.current_record}\n{traceback.format_exc()}')

        return False

    # get the overall ea:
    #  store the credits per artist
    #    skip if excluded
    #    store Written By if found
    #    check for per/track written by???
    #  Go through the tracklist
    #    If written-by isn't specified, use overall??
    #    if index track, find subtracks
    #    go through extra artists in track
    #       add writtenby/composed by to track list
    #       add other per/track roles to credits
    #    if writtenby not found (or no ea), use overall if exists?
    #  if "use master if no tracklist" go through master
    #  if "always use master if no tracklist" go through master if no tracklist
    #  if "always check master" go through master and add to roles/written by as above
    #
    #  if "use main record if no tracklist" go through mainrecord only if record and master don't have it, and main
    #  record is unique
    #  if "always check main record" go through main record (if different) and add to roles/written by as above
    #  

    def store_credits(self, record) -> bool:
        extraartists = record.data.get(API_EXTRAARTISTS)
        if not extraartists:
            self.writelog(f"No album extra artists found in {record.id}")
            return False

        if self.master:
            self.rs.ea_found_in_master = True
        else:
            self.rs.ea_found_in_record = True

        for ea in extraartists:
            ea_name = self.fix_artist_name(ea.get(API_NAME))
            ea_role = ea.get(API_ROLE, '')
            if ea_role: 
                rolelist = self.split_roles(ea_role)
                for role in rolelist:
                    if self.is_written_by_in_role(role):
                        tracks = ea.get(API_TRACKS, None)
                        if tracks:
                            self.writelog(f'Top-Level written-by/composed-by with track positions specified: {ea_name}, {role} : {tracks}')
                            # store the tracks for the artist for now so it can be processed later
                            # e.g.: "Tony Tiger" : "A1, A3 to A4"
                            self.current_record.album_written_by_tracks[ea_name] = tracks
                        else:
                            self.writelog(f'Top-Level written-by/composed-by {ea_name}: {role}')
                            if ea_name not in self.current_record.album_written_by:
                                self.current_record.album_written_by.append(ea_name)
                    if not self.ignore_role(role):
                        if role not in self.all_roles:
                            self.all_roles.append(role)
                        roles = self.current_record.credits.setdefault(ea_name, [])
                        roles.append(role)
        return True

    def store_tracklist(self, record) -> bool:
        tracklist = record.data.get(API_TRACKLIST, None)
        if not tracklist:
            self.writelog(f"No tracklist found in {record.id}")
            return False

        if self.master:
            self.rs.tl_found_in_master = True
        else:
            self.rs.tl_found_in_record = True

        for track in tracklist:
            self.store_track(track)

        # After the tracks are processed, we need to make sure the written-by is set
        # for the case where there was a "tracks" element in the album-level extraartists
        #for track_info in self.current_record.tracklist.values:
        self.check_written_by()

    def store_track(self, track):

        track_pos = track.get(API_POSITION)
        track_type = track.get(API_TYPE_)
        track_title = track.get(API_TITLE)

        track_artists = self.get_track_artists(track)

        extraartists = track.get(API_EXTRAARTISTS)

        if not track_type:
            self.writelog(f"track_type not found for {self.current_record.id}-{track_title}, pos={track_pos}")

        if track_type == API_TRACK_TYPE_INDEX:
            self.writelog(f"Index track found {track_title}, using {track_artists}")
            sts = track.get(API_TRACK_SUB_TRACKS, [])
            st_extraartists = extraartists
            for st in sts:
                st_track_pos = st.get(API_POSITION, track_pos)
                st_title = f'{track_title}-{st.get(API_TITLE)}'
                self.store_track_info(st_extraartists, st_track_pos, st_title, track_artists)
                st_extraartists = None # only store extraartists once per track

        elif track_type != API_TRACK_TYPE_TRACK:
            self.writelog(f"Skipping track type \"{track_type}\" found for {self.current_record.id}-{track_title}, pos={track_pos}")
            return False
        return self.store_track_info(extraartists, track_pos, track_title, track_artists)

    def store_track_info(self, extraartists, track_pos, track_title, track_artists):

        if not track_pos:
            self.writelog(f"Track position not found")
            return False

        if not track_title:
            self.writelog(f"Track title not found")
            return False

        ti = TrackInfo(position=track_pos, performed_by=track_artists)
        self.current_record.tracklist[track_title] =  ti
        #if not extraartists: 
        #    if self.current_record.album_written_by:
        #        self.writelog(f"Using album written by for track {track_title}: {self.current_record.album_written_by}")
        #        ti.written_by.extend(self.current_record.album_written_by)
        #    return

        if extraartists: 
            for ea in extraartists:
                ea_role = ea.get(API_ROLE)
                ea_name = self.fix_artist_name(ea.get(API_NAME))
                if ea_role: 
                    if self.master:
                        self.rs.tl_ea_found_in_master = True
                    else:
                        self.rs.tl_ea_found_in_record = True

                    #rolelist = [r.strip() for r in ea_role.split(',')]
                    rolelist = self.split_roles(ea_role)
                    for role in rolelist:
                        if not self.ignore_role(role):
                            if self.is_written_by_in_role(role):
                                if ea_name not in ti.written_by:
                                    ti.written_by.append(ea_name)
                            else:
                                roles = self.current_record.credits.setdefault(ea_name, [])
                                if role not in roles:
                                    roles.append(role)
        #if not ti.written_by:
        #    self.writelog(f"Using album written by for track {track_title}: {self.current_record.album_written_by}")
        #    ti.written_by.extend(self.current_record.album_written_by)

    def check_written_by(self):

        # Positions of existing tracks
        track_positions = [t.position for t in self.current_record.tracklist.values()]


        track_pos_to_artists= {}
        if self.current_record.album_written_by_tracks:
            # convert artists -> track_positions to track_positions -> artists
            for artist, tracks in self.current_record.album_written_by_tracks.items():
                (expanded_positions, range_found) = self.expand_tracks(tracks, track_positions)
                if not expanded_positions:
                    self.writelog(f"Could not expand tracks ({tracks}) for {artist}. Track positions={track_positions}")
                else:
                    if range_found:
                        self.writelog(f"Expanded ({tracks}) for {artist} to {expanded_positions}")
                    for p in expanded_positions:
                        written_by = track_pos_to_artists.setdefault(p, [])
                        written_by.append(artist)

        for track_title, track_info in self.current_record.tracklist.items():
            if track_info.written_by:
                continue
            written_by = track_pos_to_artists.get(track_info.position)
            if written_by:
                self.writelog(f"For track {track_title} {track_info.position} using album-level tracks written-by: {written_by}")
                track_info.written_by = written_by
                continue;
            if self.current_record.album_written_by:
                self.writelog(f"Using album written by for track {track_title}: {self.current_record.album_written_by}")
                track_info.written_by.extend(self.current_record.album_written_by)

    def csv_headers(self):
        return dict(headers)

    def split_roles(self, roles) -> []:
        pattern = r",(?![^\[]*\])"
        result = re.split(pattern, roles)
        return [s.strip() for s in result]


    def init_csv(self):
        fieldnames=self.csv_headers().keys()
        self.csv_writer = csv.DictWriter(self.out, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, delimiter=f'{CSV_COL_SEPARATOR}')
        self.csv_writer.writeheader()

    def write_csv(self):
        r = self.current_record
        row = self.csv_headers()
        row[CSV_RELEASE_ID] = f'{r.id}'
        row[CSV_ARTIST] = r.artists
        row[CSV_TITLE] = r.title
        row[CSV_FORMATS] = r.formats
        row[CSV_LABELS] = r.labels
        row[CSV_COUNTRY] = r.country
        row[CSV_YEAR] = r.year
        row[CSV_GENRES] = r.genres
        row[CSV_STYLES] = r.styles
        #row = self.csv_headers()
        row[CSV_TRACKLIST] = self.csv_tracklist(r.tracklist)
        row[CSV_CREDITS] = self.csv_credits(r.credits)
        self.csv_writer.writerow(row)
        if self.test_case:
            self.store_csv_for_test_case(r.id, row)
        
    def store_csv_for_test_case(self, id, row):
        # Temporary buffer for a single row
        rowB = io.StringIO()
        fieldnames=self.csv_headers().keys()
        writer = csv.DictWriter(rowB, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL, delimiter=f'{CSV_COL_SEPARATOR}')
    
        # Write the single row
        writer.writerow(row)
        self.csv_rows[id] = rowB.getvalue()

    def write_mrk(self):
        r = self.current_record
        mrk_lines = []

        # 035 Control Number
        mrk_lines.append(f"=035  \\\\$aTODO")
    
        # Leader & Control Fields
        #mrk_lines.append("=LDR  00000njm a2200000Ia 4500")
        
        # 100 Main Entry (Artist)
        mrk_lines.append(f"=100  1\\\\$a{r.artists}")
            
        # 245 Title

        ind2 = "4" if title.lower().startswith("the ") else "0"
        mrk_lines.append(f"=245  1{ind2}$a{r.title}")

        # 264 Label + year
        mrk_lines.append(f"=264  3\\\\$b{r.labels}$c{r.year}")

        mrk_lines.append(f"=245  1{ind2}$a{title}")
        # 300 Physical Description ($a format, $f packaging/gatefold)
        fmt = data.get("format_desc", "")
        pkg = f"$f{data['packaging']}" if data.get("packaging") else ""
        mrk_lines.append(f"=300  \\\\$a{fmt}{pkg}")
        
        
        # 505 Contents Note (One separate tag per track)
        self.mrk_tracklist(mrk_lines, tracklist)

        self.mrk_credits(mrk_lines, tracklist)
            
        # 650 Subject Headings (One tag per style)
        for style in release.get("styles", []):
            mrk_lines.append(f"=650  \\0$a{style}")
            
        # Standard MARC records in .mrk files are separated by a blank line
        #return "\n".join(mrk_lines) + "\n\n"
        mrk_lines = []
        
        # 035 System Control Number
        if data.get("control_number"):
            mrk_lines.append(f"=035  \\\\$a{data['control_number']}")
            
        # 100 Main Creator / Artist (Ind 1: 1 = Single Surname/Primary Name)
        if data.get("artist"):
            mrk_lines.append(f"=100  1\\\\$a{data['artist']}")
            
        # 245 Title (Ind 1: 1 = Added Entry, Ind 2: 4 = Non-filing chars for "The ")
        if data.get("title"):
            title = data["title"]
            ind2 = "4" if title.lower().startswith("the ") else "0"
            mrk_lines.append(f"=245  1{ind2}$a{title}")
            
        # 264 Publisher / Year
        label = data.get("label", "")
        year = data.get("year", "")
        mrk_lines.append(f"=264  3\\\\$b{label}$c{year}")
        
        # 300 Physical Description ($a format, $f packaging/gatefold)
        fmt = data.get("format_desc", "")
        pkg = f"$f{data['packaging']}" if data.get("packaging") else ""
        mrk_lines.append(f"=300  \\\\$a{fmt}{pkg}")
        
        # 505 Tracklist Note ($t Title, $r Performed by, $g Written by)
        for track in data.get("tracklist", []):
            line = f"=505  0\\\\$t{track['title']}"
            if track.get("performed_by"):
                line += f"$rPerformed by {track['performed_by']}"
            if track.get("written_by"):
                line += f"$gWritten by {track['written_by']}"
            mrk_lines.append(line)
            
        # 511 Performer Note
        if data.get("performers"):
            mrk_lines.append(f"=511  0\\\\$a{data['performers']}")
            
        # 655 Genre / Form
        if data.get("genre"):
            mrk_lines.append(f"=655  \\4$a{data['genre']['term']}$x{data['genre']['subdivision']}")

        # MarcEdit records are separated by a double newline at the end of each record
        return "\n".join(mrk_lines) + "\n\n"

    def csv_tracklist(self, tracklist) -> str:
        tracklist_str = ''
        for title, track_info in tracklist.items():
            written_by_str = ",".join(f'{w}' for w in track_info.written_by)
            if written_by_str:
                written_by_str = f'Written by {written_by_str}'
            if track_info.performed_by:
                performed_by_str = f'Performed by {track_info.performed_by}'
            else:
                performed_by_str = ''
            if tracklist_str:
                tracklist_str += f'{CSV_ITEM_SEPARATOR1}'
            tracklist_str += f'{title}{CSV_ITEM_SEPARATOR2}{performed_by_str}{CSV_ITEM_SEPARATOR2}{written_by_str}'

        return tracklist_str
    

    def mrk_tracklist(self, tracklist, mrk_lines):
        for title, track_info in tracklist.items():
            written_by_str = ",".join(f'{w}' for w in track_info.written_by)
            if written_by_str:
                written_by_str = f'Written by {written_by_str}'
            if track_info.performed_by:
                performed_by_str = f'Performed by {track_info.performed_by}'
            else:
                performed_by_str = ''
            mrk505_str = f'{title}$r{performed_by_str}$g{written_by_str}'
            mrk_lines.append(mrk505_str)

    def csv_credits(self, credits) -> str:
        credit_str = ''
        for artist, roles in credits.items():
            roles_str = ",".join(f'{r}' for r in roles)
            # What if artist is listed w/o any roles?
            if roles_str:
                roles_str = f'[{roles_str}]'
            if credit_str:
                credit_str += f'{CSV_ITEM_SEPARATOR1}'
            credit_str += f'{artist}{roles_str}'

        return credit_str

    def mrk_credits(self, credits) -> str:
        credit_str = ''
        for artist, roles in credits.items():
            roles_str = ",".join(f'{r}' for r in roles)
            # What if artist is listed w/o any roles?
            if roles_str:
                roles_str = f'[{roles_str}]'
            if credit_str:
                credit_str += f'{CSV_ITEM_SEPARATOR1}'
            credit_str += f'$a{artist}{roles_str}'

        return credit_str

    # written_by: text like: "A1, A3-A5" (or A3 to A5)
    def expand_tracks(self, tracks, track_positions):

        # Some albums label tracks with a dash. If so, don't assume it's a range
        dash_in_track_position = any("-" in tp for tp in track_positions)
        range_chars = "-|to"
        if dash_in_track_position: 
            range_chars = "to"

        expanded_positions = []
        range_found = False
        for pos in re.split(",|;", tracks):
            pos = pos.strip()
            pos_range = re.split(range_chars, pos)
            if len(pos_range) == 1:
                if pos in track_positions and pos not in expanded_positions:
                    expanded_positions.append(pos)
            elif len(pos_range) == 2:
                range_found = True
                r1 = pos_range[0].strip()
                r2 = pos_range[1].strip()
                if r1 not in track_positions:
                    return ([], range_found)
                if r2 not in track_positions:
                    return ([], range_found)
                index_low = track_positions.index(r1)
                index_high = track_positions.index(r2)
                if index_low > index_high:
                    return ([], range_found)

                expanded_positions.extend(track_positions[index_low : index_high+1])

        return expanded_positions, range_found


if __name__ == "__main__":
    tpb = OtsDiscogsToCsv()
    tpb.run()


