import discogs_client
from discogs_client.exceptions import HTTPError
import csv
import time
import argparse
import sys
import os
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
API_TRACKLIST = "tracklist"
API_TRACK_TYPE_TRACK = "track"
API_TRACK_TYPE_INDEX = "index"
API_TRACK_SUB_TRACKS = "sub_tracks"
API_ARTISTS = "artists"
API_JOIN = "join"

CSV_RELEASE_ID="release_id"
CSV_ARTIST="artist"
CSV_TITLE="title"
CSV_FORMAT="format"
CSV_QTY="qty"
CSV_FORMAT_DESCRIPTIONS="format_descriptions"
CSV_LABEL="label"
CSV_CATNO="catno"
CSV_COUNTRY="country"
CSV_YEAR="year"
CSV_GENRES="genres"
CSV_STYLES="styles"
CSV_TRACKLIST="tracklist"
CSV_CREDITS="credits"

headers = {
   CSV_RELEASE_ID : '',
   CSV_ARTIST : '',
   CSV_TITLE : '',
   CSV_FORMAT : '',
   CSV_QTY : '',
   CSV_FORMAT_DESCRIPTIONS : '',
   CSV_LABEL : '',
   CSV_CATNO : '',
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

CFG_SINGLE_ID="single_id"
CFG_INPUT_FILE="input_file"
CFG_OUTPUT_FILE="output_file"
CFG_LOG_FILE="log_file"
CFG_QUERY_FOR_IDS="query_for_ids"
CFG_IGNORE_ROLES="ignore_roles"
CFG_USER_AGENT="user_agent"
CFG_USER_TOKEN="user_token"
CFG_LOG_ALL_ROLES="log_all_roles"
CFG_NEW_RECORDS_ONLY="new_records_only"

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
class RecordInfo:
    id: int = 0

    artists: str = ''

    title: str = ''

    format: str = ''
    qty: str = ''
    format_descriptions: str = ''

    label: str = ''
    catno: str = ''

    country: str = ''
    year: str = ''

    genres: str = ''
    styles: str = ''

    tracklist:  dict = field(default_factory=dict) # name, performed by, written by

    credits: dict = field(default_factory=dict)

    master_id: int = 0

    album_written_by:  list = field(default_factory=list) 


class OtsDiscogsToCsv:
    def __init__(self, discogs_test_client=None):
        self.requests=0
        self.file=None
        self.outfile = None
        self.single_id = 0

        self.d = discogs_test_client

        self.current_record = None

        # stats
        self.records = 0

        self.has_ea_only_in_record = 0
        self.has_ea_only_in_master = 0
        self.has_ea_only_in_main_release = 0
        self.has_ea_in_record_and_master = 0
        self.no_ea = 0

        self.start = datetime.datetime.now()

        self.ignore_roles = []

        self.all_roles = []

        args = self.parse_arguments()
        output_file = None
        if args.output_file:
            output_file = args.output_file

        if args.record_id:
            self.single_id = args.record_id

        config = None
        if args.config:
            if not os.path.exists(args.config):
                print(f'Error: {args.config} does not exist')
                sys.exit(1)

            config = configparser.ConfigParser()
            config.read(args.config)

        if args.input_file:
            self.file = args.input_file

        log_file = None
        if args.log_file:
            log_file = args.log_file

        self.user_agent = None
        if args.user_agent:
            self.user_agent = args.user_agent

        self.user_token = None
        if args.user_token:
            self.user_token = args.user_token

        self.query_for_ids = False
        if args.query_for_ids:
            self.query_for_ids = True

        ignore_roles = None
        if args.ignore_roles:
            ignore_roles = args.ignore_roles.strip()

        self.log_all_roles = False
        if args.log_all_roles:
            self.log_all_roles = True

        self.new_records_only = False
        if args.new_records_only:
            self.new_records_only = True

        if config:
            if not args.record_id:
                if config.has_option(CFG_SETTINGS,CFG_SINGLE_ID):
                    self.single_id = config[CFG_SETTINGS][CFG_SINGLE_ID]
            if not args.output_file:
                if config.has_option(CFG_SETTINGS,CFG_OUTPUT_FILE):
                    self.output_file = config[CFG_SETTINGS][CFG_OUTPUT_FILE]
            if not args.input_file:
                if config.has_option(CFG_SETTINGS,CFG_INPUT_FILE):
                    self.file = args.input_file
                    self.file = config[CFG_SETTINGS][CFG_INPUT_FILE]
            if not args.log_file:
                if config.has_option(CFG_SETTINGS,CFG_LOG_FILE):
                    log_file = config[CFG_SETTINGS][CFG_LOG_FILE]
            if not args.query_for_ids:
                if config.has_option(CFG_SETTINGS,CFG_QUERY_FOR_IDS):
                    self.user_agent = config[CFG_SETTINGS][CFG_QUERY_FOR_IDS]
            if not ignore_roles:
                if config.has_option(CFG_SETTINGS,CFG_IGNORE_ROLES):
                    ignore_roles = config[CFG_SETTINGS][CFG_IGNORE_ROLES].strip()

            if not self.user_agent:
                if config.has_option(CFG_API,CFG_USER_AGENT):
                    self.user_agent = config[CFG_API][CFG_USER_AGENT]
            if not self.user_token:
                if config.has_option(CFG_API,CFG_USER_TOKEN):
                    self.user_token = config[CFG_API][CFG_USER_TOKEN]
            if not args.log_all_roles:
                if config.has_option(CFG_SETTINGS,CFG_LOG_ALL_ROLES):
                    self.user_agent = config[CFG_SETTINGS][CFG_LOG_ALL_ROLES]
            if not args.new_records_only:
                if config.has_option(CFG_SETTINGS,CFG_NEW_RECORDS_ONLY):
                    self.new_records_only = config[CFG_SETTINGS][CFG_NEW_RECORDS_ONLY]

        if ignore_roles:
            for r in ignore_roles.split(','):
                rs = r.strip()
                if rs:
                    self.ignore_roles.append(rs)

        if output_file:
            self.out = open(output_file, mode='w', encoding='utf-8')
        else:
            sys.stdout.reconfigure(encoding='utf-8') # Keep PowerShell happy!
            self.out = sys.stdout

        if log_file:
            self.log_out = open(log_file, mode='w', encoding='utf-8')
        else:
            sys.stdout.reconfigure(encoding='utf-8') # Keep PowerShell happy!
            self.log_out = self.out

        if not self.user_agent:
            print ('user_agent must be specified')
            sys.exit(1)

        if not self.user_token and self.query_for_ids:
            print ("A user token is required for the query option");
            sys.exit(1)

        if self.new_records_only and (not self.query_for_ids or not self.input_file):
            print ("New records requires an input record list and query-for-ids");
            sys.exit(1)


    def run(self):
        if not self.d:
            self.d = discogs_client.Client(self.user_agent,user_token=self.user_token)

        self.init_csv()

        if self.single_id:
            self.get_record_data(self.single_id)
            self.records = 1
            self.write_final_stats()
            return


        if self.query_for_ids:
            me = self.d.identity()
            my_releases = me.collection_folders[0].releases

            records_to_skip = [] 
            if self.new_records_only:
                with open(self.file, mode='r', newline='', encoding='utf-8') as file:
                    for row in file:
                        record_id = row.split(',', 1)[0]
                        if record_id:
                            record_id = record_id.strip()
                            record_id_i = self.to_int(record_id)
                            if record_id_i > 0:
                                records_to_skip.append(record_id_i)

            for r in my_releases:
                if r.id not in records_to_skip:
                    if self.get_record_data(r.id):
                        self.records += 1
        else:
            with open(self.file, mode='r', newline='', encoding='utf-8') as file:
                # Iterate through each row
                for row in file:
                    record_id = row.split(',', 1)[0]
                    if record_id:
                        record_id = record_id.strip()
        
                    if self.get_record_data(record_id):
                        self.records += 1

        self.write_final_stats()

    def get_record_data(self, record_id):
        try:
            record_id_i = self.to_int(record_id)

            if record_id_i == 0:
                self.writelog(f'Skipping invalid record ID {record_id}')
                return False

            self.release = self.d.release(record_id)
            self.release.refresh()

        #    self.writelog(json.dumps(self.release.data, indent=4))
        #    return

            

            ea_found_in_record = False
            ea_found_in_master = False
            ea_found_in_main_release = False
            ea_names = ""
            ea_names_per_track = ""
            ea_names_master = ""
            ea_names_per_track_master = ""

            self.requests += 1

            self.current_record = RecordInfo()
            self.current_record.id = record_id_i
            self.current_record.title = self.release.title
            self.master = False
            self.main_release = False
            self.store_record_data()
            self.write_csv()
            return

            #self.store_record_data(self.release)

            masterRec = self.release.master
            master = None
            if masterRec != None:
                self.master = True
                master = self.d.master(masterRec.id)
                master.refresh()
                ea_found_in_master  = self.get_extraartists(master)
                if master.main_release and master.main_release.id != record_id:
                    self.main_release = True
                    main_release = self.d.release(master.main_release.id)
                    main_release.refresh()
                    ea_found_in_main_release  = self.get_extraartists(main_release)


            self.print_extraartists_per_type_dups() # testing!!
            self.print_sorted_extraartists()
            tempoim = False
            if ea_found_in_record and ea_found_in_master:
                self.has_ea_in_record_and_master += 1
            elif ea_found_in_record:
                self.has_ea_only_in_record += 1
            elif ea_found_in_master:
                self.has_ea_only_in_master += 1
                tempoim = True
            elif not ea_found_in_master and not ea_found_in_record and ea_found_in_main_release:
                self.has_ea_only_in_main_release += 1
            else:
                self.no_ea += 1

            if tempoim:
                ri = "Main release is different: " if record_id != master.main_release else ''
                self.writelog(f'Note: Only found in Master {masterRec.id}')

            if master and record_id != master.main_release.id:
                    self.writelog(f"Main release in master is different: {record_id} {master.main_release.id}")

            self.writelog('')
            # temp to compare
            rlist = [];
            mlist = [];
            mrlist = []; # main release list
            if self.current_record.tracks:
                self.writelog("  Track list (release):")
                for pos,tw in sorted(self.current_record.tracks.items(), key=self.sort_track_pos):
                    title = tw[0]
                    written_by = ''
                    if tw[1]:
                        written_by = " by " + ", ".join(tw[1])
                    self.writelog(f"    {pos}. {title}{written_by}")
                    rlist.append(f"{title} by {written_by}")

            if self.current_record.tracks_master:
                self.writelog("  Track list (master):")
                for pos,tw in sorted(self.current_record.tracks_master.items(), key=self.sort_track_pos):
                    title = tw[0]
                    written_by = ''
                    if tw[1]:
                        written_by = " by " + ", ".join(tw[1])
                    self.writeln(f"    {pos}. {title}{written_by}")
                    mlist.append(f"{title} by {written_by}")
            if self.current_record.tracks_main_release:
                self.writeln("  Track list (main_release):")
                for pos,tw in sorted(self.current_record.tracks_main_release.items(), key=self.sort_track_pos):
                    title = tw[0]
                    written_by = ''
                    if tw[1]:
                        written_by = " by " + ", ".join(tw[1])
                    self.writeln(f"    {pos}. {title}{written_by}")
                    mrlist.append(f"{title} by {written_by}")
            if mlist == rlist == mrlist:
                self.writelog("Master and Release, and Main Release tracks have same writer list")
            if mlist and rlist and mrlist:
                if mlist != rlist or mlist != mrlist or mrlist != rlist:
                    self.writelog(f"Master, Release, and Main Release tracks have different writer list \n{rlist}\n{mlist}")
            if mlist and rlist:
                if mlist != rlist:
                    self.writelog(f"Master and Release tracks have different writer list \n{rlist}\n{mlist}")
                else:
                    self.writelog("Master and Release tracks have same writer list")
            elif mlist:
                    self.writelog("Only master had writer list")
            else:
                    self.writelog("Only release had writer list")
                    
            self.writeln('')
            self.writeln('')

            return True
                

        except HTTPError as e:
            # Check if the error message or status inside the exception indicates a 404
            if e.status_code == 404:
                if self.master:
                    self.writelog(f"Master of record ID {record_id} was NOT found (404 Error).")
                    return True
                self.writelog(f"Record ID {record_id} was NOT found (404 Error).")
            else:
                self.writelog(f"A different API error occurred: {e}")
            return False

    def sort_track_pos(self, item):
        key = item[0]  # Get the dictionary key
        match = re.match(r"([a-zA-Z]+)(\d+)", key)
        if match:
            alpha, num = match.groups()
            return (alpha, f'{num.zfill(5)}')  # Returns e.g., ('a', 10)
        # try 1-1 type
        match = re.match(r"(\d+)-(\d+)", key)
        if match:
            n1, n2 = match.groups()
            return (f'{n1.zfill(5)}', f'{n2.zfill(5)}')  # Returns e.g., ('a', 10)
        try:
            r = int(key)
            return ('', f'{r:05}') 
        except ValueError:
            return (key, 0)

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
                if join == ',':
                    join = ', '
                elif join:
                    join = f' {join} '
                artist_names = artist_names + join + artist_name
            else:
                artist_names = artist_name

            join = artist.get(API_JOIN, '').strip()
            if not join:
                join = ','

        return artist_names


    def store_format(self):
        if self.release.formats:
            fmt = self.release.formats[0]
            self.current_record.format = fmt.get('name', 'Unknown')
            self.current_record.qty = fmt.get('qty', '1')
            self.current_record.format_descriptions = ", ".join(fmt.get('descriptions', []))

    def store_label(self):
        if self.release.labels:
            lbl = self.release.labels[0]
            self.current_record.label = lbl.name
            self.current_record.cat_no = lbl.catno

    def get_extraartists (self, record):
        found_ea = False
        eas = record.data.get(API_EXTRAARTISTS)
        ea_names = ""

        cur_dict = self.current_record.extraartists_in_record
        if self.master:
            cur_dict = self.current_record.extraartists_in_master

        # just to see
        self.tempea_written_by = []
        self.tempeat_written_by = []

        if eas == None:
            if self.master:
                pass
        else:
            if self.master:
                self.writelog (f'Extraartists in master for record id={self.current_record.id}')
            for ea in eas:
                self.store_ea_info(ea, cur_dict)
            found_ea = True

        cur_dict = self.current_record.extraartists_per_track_in_record
        if self.master:
            cur_dict = self.current_record.extraartists_per_track_in_master

        # check tracklist to see if extraartists exists
        tls = record.tracklist
        for tl in tls or []:
            found_ea |= self.store_ea_info_per_track(tl, cur_dict)

        if len(self.tempea_written_by) > 0 and len(self.tempeat_written_by) == 0:
            self.writelog(f"Record {self.current_record.id} contains written-by only in ea")

        if len(self.tempea_written_by) > 0 and len(self.tempeat_written_by) > 0 and (Counter(self.tempea_written_by) != Counter(self.tempeat_written_by)): 
            self.writelog(f"Record {self.current_record.id} written-by doesn't match\n{self.tempea_written_by}\n{self.tempeat_written_by}")

        return found_ea

    def fix_artist_name(self, artist_name):
        if artist_name == None:
            return ''
        pattern = r"\s*\(\d+\)\s*$"
        return re.sub(pattern, '', artist_name)

    def store_ea_info(self, ea, ea_dict):
        # ea_dict is artist : roles
        artist_name = ea["name"]
        if artist_name == None:
            self.writelog(f'Error: name not found in extraartists entry')
            return
        artist_name = self.fix_artist_name(artist_name)
        # adds artist name and list/dict of roles, returned in ea_entry
        # see if role exists in discogs
        role = ea[API_ROLE]
        # TODO: store written by? Or is this always per track?
        #if role and not self.ignore_role(role) and role != API_WRITTEN_BY:
        if role and not self.ignore_role(role):
            if self.is_written_by_in_role(role):
            #if False: # temp
                if artist_name not in self.tempea_written_by:
                    self.tempea_written_by.append(artist_name)
            else:
                ea_entry = ea_dict.setdefault(artist_name, {})
                current_tracks = ea_entry.setdefault(role,  {})
                # adds role to ea_entry with a list/dict of tracks, returned in current_tracks
                #current_tracks = roles.setdefault(role, {})
                tracks = ea["tracks"]
                if tracks:
                    trackList = [t.strip() for t in ea["tracks"].split(',')]
                    for t in trackList or []:
                        current_tracks[t] = None
                        #roles.update(dict.fromkeys(tracks))

    def is_written_by_in_role(self, role):
        if API_WRITTEN_BY.casefold() in role.casefold() or API_WRITTEN_BY_NO_DASH.casefold() in role.casefold():
            return True
        if API_COMPOSED_BY.casefold() in role.casefold() or API_COMPOSED_BY_NO_DASH.casefold() in role.casefold():
            return True
        return False

    def store_ea_info_per_track(self, tl, ea_dict):
        eats = tl.data.get(API_EXTRAARTISTS)
        track_pos = tl.data.get(API_POSITION)
        track_type = tl.data.get(API_TYPE_)
        track_title = tl.data.get(API_TITLE)
        track_artist = tl.data.get(API_NAME)
        if not track_artist:
            track_artist = self.current_record.artists

        if not track_type:
            self.writelog(f"track_type not found for {self.current_record.id}-{track_title}, pos={track_pos}")

        if track_type == API_TRACK_TYPE_INDEX:
            sts = tl.data.get(API_TRACK_SUB_TRACKS, [])
            for st in sts:
                st_title = f'{track_title}-{st.get(API_TITLE)}'
                st_track_pos = st.get(API_POSITION, track_pos)
                st_track_artist = st.get(API_POSITION, track_artist)
                self.store_track_info(eats, ea_dict, st_track_pos, st_title, st_track_artist)

        elif track_type != API_TRACK_TYPE_TRACK:
            self.writelog(f"Skipping track type \"{track_type}\" found for {self.current_record.id}-{track_title}, pos={track_pos}")
            return False
        return self.store_track_info(eats, ea_dict, track_pos, track_title, track_artist)

    def store_track_info(self, ea_dict, eats, track_pos, track_title, track_artists):

        if not track_pos:
            self.writelog(f"track position not found")
            return False

        written_by = []
        # temp code to compare release and master
        if self.main_release: 
            if track_pos not in self.current_record.tracks_main_release:
                self.current_record.tracks_main_release[track_pos] = (track_title, written_by)
            else:
                written_by = self.current_record.tracks_main_release[track_pos][1]
        elif self.master: 
            if track_pos not in self.current_record.tracks_master:
                self.current_record.tracks_master[track_pos] = (track_title, written_by)
            else:
                written_by = self.current_record.tracks_master[track_pos][1]
        else:
            if track_pos not in self.current_record.tracks:
                self.current_record.tracks[track_pos] = (track_title, written_by)
            else:
                written_by = self.current_record.tracks[track_pos][1]

        if eats == None:
            return False

        for ea in eats:
            artist_name = ea["name"]
            if artist_name == None:
                self.writelog(f'Error: name not found in extraartists entry')
                continue
            artist_name = self.fix_artist_name(artist_name)
            role = ea[API_ROLE]
            if role and not self.ignore_role(role):
                if self.is_written_by_in_role(role):
                #if False:
                    if artist_name not in self.tempea_written_by:
                        self.tempeat_written_by.append(artist_name)
                    if artist_name not in written_by:
                        written_by.append(artist_name)
                else:
                    ea_entry = ea_dict.setdefault(artist_name, {})
                    current_tracks = ea_entry.setdefault(role,  {})
                    current_tracks[track_pos] = None
        return True


    def parse_arguments(self):
        """
        Handles command-line arguments for the Discogs script.
        """
        parser = argparse.ArgumentParser(
            description="Fetch record data from Discogs API and save to a file."
        )

        # Group for input options (Mutually exclusive means you must pick ONE)
        input_group = parser.add_mutually_exclusive_group(required=True)
        
        input_group.add_argument(
            '-i', '--input-file', 
            type=str, 
            help="Path to the input file containing a list of Discogs IDs."
        )
        
        input_group.add_argument(
            '-id', '--record-id', 
            type=int, 
            help="A single Discogs Record/Release ID to process."
        )
        
        input_group.add_argument(
            '-qi', '--query-for-ids', 
            action='store_true',
            help="Query discogs for the record_ids. user_token must be specified"
        )

        # Argument for the output file destination
        parser.add_argument(
            '-o', '--output-file', 
            type=str, 
            help="Path to the output text/CSV file where results will be saved."
        )

        parser.add_argument(
            '-l', '--log-file', 
            type=str, 
            help="Path to the file where log messages will be saved."
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
            help="User-Agent to use for authenicated API request"
        )

        parser.add_argument(
            '-ir', '--ignore-roles', 
            type=str, 
            help="A list of comma-separated roles to ignore"
        )

        parser.add_argument(
            '-lar', '--log-all-roles', 
            action='store_true', 
            help="Log all roles encountered, not including ignored roles"
        )

        parser.add_argument(
            '-nro', '--new-records-only', 
            action='store_true', 
            help="Only get records that aren't in the input list. Requires --query-for-ids"
        )

        # Parse the arguments from the command line
        return parser.parse_args()

    def write_final_stats(self):
        self.writelog(f'Total Records={self.records}')
        self.writelog(f'Extra Artists: found in both={self.has_ea_in_record_and_master} Record only={self.has_ea_only_in_record} Master only={self.has_ea_only_in_master} Nt found={self.no_ea} Main release only={self.has_ea_only_in_main_release}')
        time_difference = datetime.datetime.now() - self.start
        if self.log_all_roles:
            self.log_all_roles_found()
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

    def print_extraartists_per_type (self):
        self.writeln("  Release Record Extra Artists")
        self.print_extraartists(self.current_record.extraartists_in_record)
        self.writeln("\n  Release Record Extra Artists Per Track")
        self.print_extraartists(self.current_record.extraartists_per_track_in_record)
        self.writeln("\n  Master Record Extra Artists")
        self.print_extraartists(self.current_record.extraartists_in_master)
        self.writeln("\n  Master Record Extra Artists Per Track")
        self.print_extraartists(self.current_record.extraartists_per_track_in_master)

    def print_extraartists (self, entry):
        artist = '' 
        for a, role_dict in entry.items():
            artist = a
            roles = []
            for r, track_dict in role_dict.items():
                if track_dict:
                    tracks = ",".join(track_dict.keys())
                    if tracks:
                        r += (f' ({tracks})')
                roles.append(r)
            self.writeln(f"    {artist}: {','.join(roles)}")

    # test code to show duplicates 
    def print_extraartists_per_type_dups (self):
        ea_list_as_string = [
        [],
        [],
        [],
        []]


        self.writeln("  Release Record Extra Artists")
        self.print_extraartists_dups(self.current_record.extraartists_in_record, 0, ea_list_as_string)
        self.writeln("\n  Release Record Extra Artists Per Track")
        self.print_extraartists_dups(self.current_record.extraartists_per_track_in_record, 1, ea_list_as_string)
        self.writeln("\n  Master Record Extra Artists")
        self.print_extraartists_dups(self.current_record.extraartists_in_master, 2, ea_list_as_string)
        self.writeln("\n  Master Record Extra Artists Per Track")
        self.print_extraartists_dups(self.current_record.extraartists_per_track_in_master, 3, ea_list_as_string)

    def print_extraartists_dups (self, entry, index, ea_list_as_string):
        artist = '' 
        dup_found = False
        uniq_found = False
        for a, role_dict in entry.items():
            artist = a
            roles = []
            for r, track_dict in role_dict.items():
                if track_dict:
                    tracks = ",".join(track_dict.keys())
                    if tracks:
                        r += (f' ({tracks})')
                roles.append(r)
            
            a_r = f"{artist}: {','.join(roles)}"
            elas = ea_list_as_string[index]
            elas.append(a_r)
            i, dup  = self.check_for_dup(a_r, index, ea_list_as_string)
            dup_location = '' 
            if dup:
                dup_found = True
                if i == 0:
                    dup_location = "* ear"
                elif i == 1:
                    dup_location = "** ert"
                elif i == 2:
                    dup_location = "*** eam"
            else:
                uniq_found = True
            
            self.writeln(f"    {a_r}{dup_location}")
        if dup_found and uniq_found:
            self.writelog(f" Found some duplicates")
        elif dup_found:
            self.writelog(f" Found all duplicates")
        else:
            self.writelog(f" Found no duplicates")


    def check_for_dup(self, a_r, index, ea_list_as_string):
        if index == 0: 
            return 0, False
        for ll in range(0,index):
            if a_r in ea_list_as_string[ll]: 
                return ll, True
        return 0, False

    def print_sorted_extraartists (self):
        self.writeln('\n  Sorted Extra Artists')
        types = [
                ("ear", self.current_record.extraartists_in_record),
                ("ert", self.current_record.extraartists_per_track_in_record),
                ("eam", self.current_record.extraartists_in_master),
                ("emt", self.current_record.extraartists_per_track_in_master)
                ]

        if not self.current_record.extraartists_per_track_in_record:
            if self.current_record.extraartists_per_track_in_master:
                self.writelog(f'Only master {self.current_record.master_id} contained a tracklist ')
            else:
                self.writelog(f'No tracklist found in record (or master) {self.current_record.master_id}')


        all_eas = []
        for p_e in types:
            all_eas.extend(self.get_extraartists_in_entry(p_e[0], p_e[1]))

        # analyze written-by
        # First, see if there are any "Written-By" in the top level without tracklists
        for artist, roles in types[0][1].items():
            for role,pos in roles.items(): 
                if self.is_written_by_in_role(role):
                    if pos:
                        self.writelog(f'Record {self.current_record.id} contains top-level "written by" for {artist} with tracklist: {role} {pos}')
                    else:
                        self.writelog(f'Record {self.current_record.id} contains top-level "written by" for {artist}: {role}')

        # See if "written by" with song positions are found in release and master, and how they compare
        release_wb = {} 
        for artist, roles in types[1][1].items():
            for role,pos in roles.items(): 
                if self.is_written_by_in_role(role) and pos:
                    release_wb[artist] = (role, pos)

        master_wb = {} 
        mismatch_found = False
        for artist, roles in types[3][1].items():
            for role,pos in roles.items(): 
                if self.is_written_by_in_role(role) and pos:
                    mrp = (role,pos)
                    master_wb[artist] = mrp
                    if artist in release_wb:
                        if mrp != release_wb[artist]:
                            self.writelog (f'Mismatch between eat and emt for {artist} written-by in record {self.current_record.id} {release_wb[artist]} {mrp}')
                        else:
                            pass
                            #self.writelog (f'Match between eat and emt for {artist} written-by in record {self.current_record.id} {release_wb[artist]} {mrp}')

        if release_wb and master_wb:
            self.writelog (f'Both master and release contain per/track written-by, mismatch={mismatch_found}')
        elif release_wb and not master_wb:
            self.writelog (f'Only release contains per/track written-by')
        elif not release_wb and master_wb:
            self.writelog (f'Only master contains per/track written-by')
        else:
            self.writelog (f'Neither release nor master contain per/track written-by')

        for p_e in types:
            all_eas.extend(self.get_extraartists_in_entry(p_e[0], p_e[1]))

        all_eas.sort(key=lambda x: x.split(":", maxsplit=1)[1])
        for e in all_eas:
            self.writeln(e)



    def get_extraartists_in_entry (self, prefix, entry):
        artist = '' 
        all_ea = []
        for a, role_dict in entry.items():
            artist = a
            roles = []
            for r, track_dict in role_dict.items():
                if track_dict:
                    tracks = ",".join(track_dict.keys())
                    if tracks:
                        r += (f' ({tracks})')
                roles.append(r)
            all_ea.append(f"    {prefix}: {artist}: {','.join(roles)}")
        return all_ea


    def ignore_role(self, role):
        if not self.ignore_roles:
            return False
        for r in self.ignore_roles:
            if r.casefold() in role.casefold():
                return True
        return False
        #return any(r.casefold() in role.casefold() for r in self.ignore_roles)

    def to_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def store_record_data(self) -> bool:
        try:
            self.store_album_artists()

            self.current_record.title = self.release.title

            self.store_format()

            self.store_label()

            self.current_record.country = self.release.country or ''

            self.current_record.year = self.release.year or ''

            self.current_record.genres = ", ".join(self.release.genres or [])

            self.current_record.styles = ", ".join(self.release.styles or [])

            self.store_credits(self.release)

            self.store_tracklist(self.release)

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

        for ea in extraartists:
            ea_name = self.fix_artist_name(ea.get(API_NAME))
            ea_role = ea.get(API_ROLE, '')
            if ea_role: 
                #rolelist = [r.strip() for r in ea_role.split(',')]
                rolelist = self.split_roles(ea_role)
                for role in rolelist:
                    if self.is_written_by_in_role(role):
                        self.writelog(f'Top-Level written-by/composed-by {role}')
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

        for track in tracklist:
            self.store_track(track)

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

        written_by = []
        self.current_record.tracklist[track_title] =  (track_artists, written_by)
        if not extraartists: 
            #self.writelog(f"Extra artists not found for track {track_title}")
            if self.current_record.album_written_by:
                self.writelog(f"Using album written by for track {track_title}: {self.current_record.album_written_by}")
                written_by.extend(self.current_record.album_written_by)
            return

        for ea in extraartists:
            ea_role = ea.get(API_ROLE)
            ea_name = self.fix_artist_name(ea.get(API_NAME))
            if ea_role: 
                #rolelist = [r.strip() for r in ea_role.split(',')]
                rolelist = self.split_roles(ea_role)
                for role in rolelist:
                    if not self.ignore_role(role):
                        if self.is_written_by_in_role(role):
                            if ea_name not in written_by:
                                written_by.append(ea_name)
                        else:
                            roles = self.current_record.credits.setdefault(ea_name, [])
                            if role not in roles:
                                roles.append(role)
        if not written_by:
            self.writelog(f"Using album written by for track {track_title}: {self.current_record.album_written_by}")
            written_by.extend(self.current_record.album_written_by)

    def csv_headers(self):
        return dict(headers)

    def split_roles(self, roles) -> []:
        pattern = r",(?![^\[]*\])"
        result = re.split(pattern, roles)
        return [s.strip() for s in result]


    def init_csv(self):
        fieldnames=self.csv_headers().keys()
        self.csv_writer = csv.DictWriter(self.out, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        self.csv_writer.writeheader()

    def write_csv(self):
        r = self.current_record
        row = self.csv_headers()
        row[CSV_RELEASE_ID] = f'{r.id}'
        row[CSV_ARTIST] = r.artists
        row[CSV_TITLE] = r.title
        row[CSV_FORMAT] = r.format
        row[CSV_QTY] = r.qty
        row[CSV_FORMAT_DESCRIPTIONS] = r.format_descriptions
        row[CSV_LABEL] = r.label
        row[CSV_CATNO]= r.catno
        row[CSV_COUNTRY] = r.country
        row[CSV_YEAR] = r.year
        row[CSV_GENRES] = r.genres
        row[CSV_STYLES] = r.styles
        #row = self.csv_headers()
        row[CSV_TRACKLIST] = self.csv_tracklist(r.tracklist)
        row[CSV_CREDITS] = self.csv_credits(r.credits)
        self.csv_writer.writerow(row)
        
    def csv_tracklist(self, tracklist) -> str:
        tracklist_str = ''
        for title, (performed_by, written_by) in tracklist.items():
            written_by_str = ",".join(f'{w}' for w in written_by)
            if written_by_str:
                written_by_str = f'Written by {written_by_str}'
            if performed_by:
                performed_by_str = f'Performed by {performed_by}'
            else:
                performed_by_str = ''
            if tracklist_str:
                tracklist_str += '|'
            tracklist_str += f'{title};{performed_by_str};{written_by_str}'

        return tracklist_str

    def csv_credits(self, credits) -> str:
        credit_str = ''
        for artist, roles in credits.items():
            roles_str = ",".join(f'{r}' for r in roles)
            # What if artist is listed w/o any roles?
            if roles_str:
                roles_str = f'[{roles_str}]'
            if credit_str:
                credit_str += '|'
            credit_str += f'{artist}{roles_str}'

        return credit_str


if __name__ == "__main__":
    tpb = OtsDiscogsToCsv()
    tpb.run()


