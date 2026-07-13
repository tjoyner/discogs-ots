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
from collections import Counter

# temp fix for encoding: $env:PYTHONIOENCODING="utf-8"
#                        or set pythonencoding="utf-8"
# or: python your_script.py | Out-File -Encoding utf8 output.txt
API_ROLE = "role"
API_WRITTEN_BY = "Written-By"
API_WRITTEN_BY_NO_DASH = "Written By"
API_POSITION = "position"
API_EXTRAARTISTS = "extraartists"
API_TYPE_ = "type_"
API_TITLE = "title"
API_NAME = "name"
API_TRACK_TYPE_TRACK = "track"
API_TRACK_TYPE_INDEX = "index"
API_TRACK_SUB_TRACKS = "sub_tracks"

CFG_SETTINGS="settings"
CFG_API="api"

CFG_SINGLE_ID="single_id"
CFG_INPUT_FILE="input_file"
CFG_OUTPUT_FILE="output_file"
CFG_QUERY_FOR_IDS="query_for_ids"
CFG_IGNORE_ROLES="ignore_roles"
CFG_USER_AGENT="user_agent"
CFG_USER_TOKEN="user_token"

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
    record_id: int = 0
    title: str = ""
    master_id: int = 0
    tracks:  dict = field(default_factory=dict) # id and title
    tracks_master:  dict = field(default_factory=dict) # temp
    tracks_main_release:  dict = field(default_factory=dict) # temp
    extraartists_in_record: dict = field(default_factory=dict)
    extraartists_per_track_in_record: dict = field(default_factory=dict)
    extraartists_in_master: dict = field(default_factory=dict)
    extraartists_per_track_in_master: dict = field(default_factory=dict)
    artists: str = ""

class OtsDiscogsToCsv:
    def __init__(self, discogs_test_client=None):
        self.requests=0
        #self.file = '../Discogs-csv2026-03-19-1 - test.csv'
        self.file = '../Discogs-csv2026-03-19-1.csv'
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

        self.ignore_roles = None

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

        self.user_agent = None
        if args.user_agent:
            self.user_agent = args.user_agent

        self.user_token = None
        if args.user_token:
            self.user_token = args.user_token

        self.query_for_ids = False
        if args.query_for_ids:
            self.query_for_ids = True

        if args.ignore_roles:
            self.ignore_roles =  [r.strip() for r in args.ignore_roles.split(',')]

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
            if not args.query_for_ids:
                if config.has_option(CFG_SETTINGS,CFG_QUERY_FOR_IDS):
                    self.user_agent = config[CFG_SETTINGS][CFG_QUERY_FOR_IDS]
            if not self.ignore_roles:
                if config.has_option(CFG_SETTINGS,CFG_IGNORE_ROLES):
                    ir = config[CFG_SETTINGS][CFG_IGNORE_ROLES]
                    self.ignore_roles =  [r.strip() for r in ir.split(',')]

            if not self.user_agent:
                if config.has_option(CFG_API,CFG_USER_AGENT):
                    self.user_agent = config[CFG_API][CFG_USER_AGENT]
            if not self.user_token:
                if config.has_option(CFG_API,CFG_USER_TOKEN):
                    self.user_token = config[CFG_API][CFG_USER_TOKEN]

        if output_file:
            self.out = open(args.output_file, mode='w', encoding='utf-8')
        else:
            sys.stdout.reconfigure(encoding='utf-8') # Keep PowerShell happy!
            self.out = sys.stdout

        if not self.user_agent:
            print ('user_agent must be specified')
            sys.exit(1)

        if not self.user_token and self.query_for_ids:
            print ("A user token is required for the query option");
            sys.exit(1)


    def run(self):
        if not self.d:
            self.d = discogs_client.Client(self.user_agent,user_token=self.user_token)
        if self.single_id:
            self.get_record_data(self.single_id)
            self.records = 1
            self.write_final_stats()
            return

        if self.query_for_ids:
            me = self.d.identity()
            my_releases = me.collection_folders[0].releases

            for r in my_releases:
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
                self.writelog(f"Skipping invalid record ID {record_id}")
                return False

            #self.writeln(f"\nGetting Release for {record_id}")
            self.release = self.d.release(record_id)
            self.release.refresh()

            #self.writeln(self.process_release_data(record_id_i, self.release))

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
            self.store_record_data()
            self.master = False
            self.main_release = False

            ea_found_in_record = self.get_extraartists(self.release)
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


            self.writeln(f'{self.current_record.title} {self.current_record.id}')
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

            self.writeln('')
            # temp to compare
            rlist = [];
            mlist = [];
            mrlist = []; # main release list
            if self.current_record.tracks:
                self.writeln("  Track list (release):")
                for pos,tw in sorted(self.current_record.tracks.items(), key=self.sort_track_pos):
                    title = tw[0]
                    written_by = ''
                    if tw[1]:
                        written_by = " by " + ", ".join(tw[1])
                    self.writeln(f"    {pos}. {title}{written_by}")
                    rlist.append(f"{title} by {written_by}")

            if self.current_record.tracks_master:
                self.writeln("  Track list (master):")
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

    def store_record_data(self):
        artist_names = [self.fix_artist_name(artist.name) for artist in self.release.artists]
        self.artists = ", ".join(artist_names)
        self.writelog(f"Storing artists as {self.artists}")

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
                st_title = st.get(API_TITLE)
                self.writelog(f'Tom: subtrack {track_title}-{st_title}\n {st}')
                self.writelog(f'Tom: track eats: {eats}')
                self.writelog(f'Tom: subtrack eats: {st.get(API_EXTRAARTISTS)}')

        elif track_type != API_TRACK_TYPE_TRACK:
            self.writelog(f"Skipping track type \"{track_type}\" found for {self.current_record.id}-{track_title}, pos={track_pos}")
            return False

        if not track_pos:
            self.writelog(f"track position not found for {tl}")
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

        # Parse the arguments from the command line
        return parser.parse_args()

    def write_final_stats(self):
        self.writeln(f'Total Records={self.records}')
        self.writeln(f'Extra Artists: found in both={self.has_ea_in_record_and_master} Record only={self.has_ea_only_in_record} Master only={self.has_ea_only_in_master} Nt found={self.no_ea} Main release only={self.has_ea_only_in_main_release}')
        time_difference = datetime.datetime.now() - self.start
        self.writeln(f'Total time: {time_difference}')

    def writeln(self, text=""):
        self.out.write(f"{text}\n")

    def writelog(self, text=""):
        id = self.current_record.id if self.current_record.id else ''
        padded_id = f"{id:>8}"
        self.out.write(f"{padded_id}: {text}\n")

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
        return any(role.casefold() == r.casefold() for r in self.ignore_roles)

    def to_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
        import re

    def process_release_data(self, release_id: int, release) -> dict:
        try:
            # 1. Clean the Artist Name (Strips Discogs numbering like 'Artist (2)' to 'Artist')
            artist_raw = release.artists[0].name if release.artists else "Unknown"
            artist = self.fix_artist_name(artist_raw)

            title = release.title

            # 2. Extract Format details safely
            format_name = "Unknown"
            format_qty = "1"
            format_descriptions = ""
            
            if release.formats:
                fmt = release.formats[0]
                format_name = fmt.get('name', 'Unknown')
                format_qty = fmt.get('qty', '1')
                # Join multiple descriptions into a single comma-separated string
                format_descriptions = ", ".join(fmt.get('descriptions', []))

            # 3. Extract Label and Catalog Number safely
            label_name = "Unknown"
            cat_no = "Unknown"
            
            if release.labels:
                lbl = release.labels[0]
                label_name = lbl.name
                cat_no = lbl.catno

            # 4. Extract Barcode identifier safely from lists of notes/identifiers
            barcode = "Unknown"
            if hasattr(release, 'identifiers'):
                for i in release.identifiers:
                    if i.get('type') == 'Barcode':
                        barcode = i.get('value', 'Unknown')
                        break

            # 5. Build the Tracklist string (Tracks separated by pipes '|' or newlines)
            track_list = []
            if release.tracklist:
                for track in release.tracklist:
                    # Skips index headings and tracks missing titles
                    if track.title and track.position:
                        track_list.append(f"{track.position}. {track.title}")
                        if track.credits:
                            for a in release.credits:
                                print (f'tom-per track: {a.name} {a.role}')
            tracklist_string = " | ".join(track_list)

            for a in release.credits:
                print (f'tom: {a.name} {a.role}')

            # 6. Map everything into a flat row matching ROW_NAMES schema
            return {
                "release_id": str(release_id),
                "artist": artist,
                "title": title,
                "format": format_name,
                "qty": str(format_qty),
                "format_descriptions": format_descriptions,
                "label": label_name,
                "catno": cat_no,
                "country": release.country or '',
                "year": release.year or '',
                "genres": ", ".join(release.genres or []),
                "styles": ", ".join(release.styles or []),
                "barcode": barcode,
                "tracklist": tracklist_string
            }

        except Exception as e:
            # Gracefully handle any unexpected extraction crash
            return {
                "release_id": str(release_id),
                "artist": f"ERROR: Could not parse ({str(e)})",
                "format": "", "qty": "", "format_descriptions": "", "label": "",
                "catno": "", "country": "", "year": "", "genres": "", "styles": "",
                "barcode": "", "tracklist": ""
            }

if __name__ == "__main__":
    tpb = OtsDiscogsToCsv()
    tpb.run()


