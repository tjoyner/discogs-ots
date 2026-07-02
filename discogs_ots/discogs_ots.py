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

# temp fix for encoding: $env:PYTHONIOENCODING="utf-8"
#                        or set pythonencoding="utf-8"
# or: python your_script.py | Out-File -Encoding utf8 output.txt

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
    extraartists_in_record: dict = field(default_factory=dict)
    extraartists_per_track_in_record: dict = field(default_factory=dict)
    extraartists_in_master: dict = field(default_factory=dict)
    extraartists_per_track_in_master: dict = field(default_factory=dict)

class OtsDiscogsToCsv:
    def __init__(self):
        self.requests=0
        #self.file = '../Discogs-csv2026-03-19-1 - test.csv'
        self.file = '../Discogs-csv2026-03-19-1.csv'
        self.outfile = None
        self.single_id = 0

        self.current_record = None

        # stats
        self.records = 0

        self.has_ea_only_in_record = 0
        self.has_ea_only_in_master = 0
        self.has_ea_in_record_and_master = 0
        self.no_ea = 0

        self.start = datetime.datetime.now()

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

        if config:
            if not args.record_id:
                self.single_id = config["settings"]["single_id"]
            if not args.output_file:
                self.output_file = config["settings"]["output_file"]
            if not args.input_file:
                self.file = args.input_file
                self.file = config["settings"]["input_file"]
            if not args.query_for_ids:
                self.user_agent = config['settings']['query_for_ids']
            if not self.user_agent:
                self.user_agent = config['api']['user_agent']
            if not self.user_token:
                self.user_token = config['api']['user_token']

        if output_file:
            self.out = open(args.output_file, mode='w', encoding='utf-8') # temp!!
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
                # Set up the DictReader
                # FIXME: just read line by line?
                csv_reader = csv.DictReader(file)
                
                # Iterate through each row
                for row in csv_reader:
                    # Access columns directly by their header names
                    record_id = row['release_id']
                    
                    if self.get_record_data(record_id):
                        self.records += 1

        self.write_final_stats()

    def get_record_data(self, record_id):
        try:
            record_id_i = self.to_int(record_id)

            if record_id_i == 0:
                self.writeln(f"Skipping invalid record ID {record_id}")
                return False

            #self.writeln(f"\nGetting Release for {record_id}")
            self.release = self.d.release(record_id)
            self.release.refresh()

            ea_found_in_record = False
            ea_found_in_master = False
            ea_names = ""
            ea_names_per_track = ""
            ea_names_master = ""
            ea_names_per_track_master = ""

            self.requests += 1

            self.current_record = RecordInfo()
            self.current_record.record_id = record_id_i
            self.current_record.title = self.release.title
            self.master = False

            #self.writeln (f"requests={self.requests} record_id={record_id}")
            ea_found_in_record = self.get_extraartists(self.release)
            #self.writeln(f"\nGetting Master for {record_id}")
            masterRec = self.release.master
            if masterRec != None:
                self.master = True
                master = self.d.master(masterRec.id)
                master.refresh()
                ea_found_in_master  = self.get_extraartists(master)

            #self.writeln(f'{self.release.title}, {ea_names}, {ea_names_per_track}  {ea_names_master}, {ea_names_per_track_master}')

            self.writeln(f'{self.current_record.title} {self.current_record.record_id}')
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
            else:
                self.no_ea += 1

            self.writeln(f'{"Note: Only found in Master)" if tempoim else ""}')
            self.writeln('')
            if self.current_record.tracks:
                self.writeln("  Track list:")
                for pos,title in sorted(self.current_record.tracks.items(), key=self.sort_track_pos):
                    self.writeln(f"    {pos}. {title}")
                    
            self.writeln('')
            self.writeln('')

            return True
                

        except HTTPError as e:
            # Check if the error message or status inside the exception indicates a 404
            if e.status_code == 404:
                self.writeln(f"Record ID {record_id} was NOT found (404 Error).")
            else:
                self.writeln(f"A different API error occurred: {e}")
            return False

    def sort_track_pos(self, item):
        key = item[0]  # Get the dictionary key
        match = re.match(r"([a-zA-Z]+)(\d+)", key)
        if match:
            alpha, num = match.groups()
            return (alpha, int(num))  # Returns e.g., ('a', 10)
        try:
            r = int(key)
            return ('', r) 
        except ValueError:
            return (key, 0)
        

    def get_extraartists (self, record):
        found_ea = False
        eas = record.data.get('extraartists')
        ea_names = ""

        cur_dict = self.current_record.extraartists_in_record
        if self.master:
            cur_dict = self.current_record.extraartists_in_master

        if eas == None:
            if self.master:
                pass
            #self.writeln (f'No extraartists for record id={record.id}')
        else:
            if self.master:
                self.writeln (f'Extraartists in master for record id={self.current_record.record_id}')
            for ea in eas:
                self.store_ea_info(ea, cur_dict)
        #    ea_names = "|".join(f'{ea["role"]} : {ea["name"]}' for ea in eas)
        #    self.writeln (f"cn={ea_names}")
            found_ea = True

        cur_dict = self.current_record.extraartists_per_track_in_record
        if self.master:
            cur_dict = self.current_record.extraartists_per_track_in_master

        # check tracklist to see if extraartists exists
        tls = record.tracklist
        for tl in tls or []:
            found_ea |= self.store_ea_info_per_track(tl, cur_dict)
            #eats = tl.data.get('extraartists')
            #if eats != None:
            #   # self.writeln (f'ea exists in track {tl}: {eats}')
            #    found_ea = True
            #    for eat in eats:
            #        artists_per_tl[eat['name']] = eat['role']

        #ea_names_per_track = "|".join(f'{r} : {a}' for a,r in artists_per_tl.items())
        #self.writeln (f"cntl={combined_names}")
        #self.writeln(f'{pprint.pformat(cur_dict)}')
        #self.writeln('')

        return found_ea

    def remove_trailing_parens(self, artist_name):
        pattern = r"\s*\(\d+\)$"
        return re.sub(pattern, '', artist_name)

    def store_ea_info(self, ea, ea_dict):
        # ea_dict is artist : roles
        artist_name = ea["name"]
        if artist_name == None:
            self.writeln(f'Error: name not found in extraartists entry')
            return
        artist_name = self.remove_trailing_parens(artist_name)
        ea_entry = ea_dict.setdefault(artist_name, {})
        # adds artist name and list/dict of roles, returned in ea_entry
        # see if role exists in discogs
        role = ea["role"]
        if role:
            current_tracks = ea_entry.setdefault(role,  {})
            # adds role to ea_entry with a list/dict of tracks, returned in current_tracks
            #current_tracks = roles.setdefault(role, {})
            tracks = ea["tracks"]
            if tracks:
                trackList = [t.strip() for t in ea["tracks"].split(',')]
                for t in trackList or []:
                    current_tracks[t] = None
                    #roles.update(dict.fromkeys(tracks))

    def store_ea_info_per_track(self, tl, ea_dict):
        eats = tl.data.get('extraartists')
        track_pos = tl.data.get('position')
        track_type = tl.data.get('type_')
        track_title = tl.data.get('title')
        if not track_type or track_type != "track":
            self.writeln(f"Skipping track type \"{track_type}\" found for {track_title}, pos={track_pos}")
            return False
        if not track_pos:
            self.writeln(f"track position not found for {tl}")
            return False

        if track_pos not in self.current_record.tracks:
            self.current_record.tracks[track_pos] = track_title

        if eats == None:
            #self.writeln(f'Error: No Extra Artists in tracklist')
            return False

        for ea in eats:
            artist_name = ea["name"]
            if artist_name == None:
                self.writeln(f'Error: name not found in extraartists entry')
                continue
            artist_name = self.remove_trailing_parens(artist_name)
            ea_entry = ea_dict.setdefault(artist_name, {})
            role = ea["role"]
            if role:
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

        # Parse the arguments from the command line
        return parser.parse_args()

    def write_final_stats(self):
        self.writeln(f'Total Records={self.records}')
        self.writeln(f'Extra Artists: found in both={self.has_ea_in_record_and_master} Record only={self.has_ea_only_in_record} Master only={self.has_ea_only_in_master} Nt found={self.no_ea}')
        time_difference = datetime.datetime.now() - self.start
        self.writeln(f'Total time: {time_difference}')

    def writeln(self, text=""):
        """Helper function to automatically append a newline to a stream."""
        self.out.write(f"{text}\n")

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

    # test code to show duplicates in different colors
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
            dup_location = '' # asterisks
            if dup:
                if i == 0:
                    dup_location = "* ear"
                elif i == 1:
                    dup_location = "** ert"
                elif i == 2:
                    dup_location = "*** eam"
            
            self.writeln(f"    {a_r}{dup_location}")

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

        all_eas = []
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


    def to_int(self, value):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

if __name__ == "__main__":
    tpb = OtsDiscogsToCsv()
    tpb.run()



#d = discogs_client.Client('BrightestThingsExample/0.1')
#release = d.release(1799382)
#
#print(release.master.id)
#master = d.master(release.master.id)
#tls = master.tracklist
#
#for tl in tls:
#    print(tl.fetch('extraartists'))
#
#eas = release.fetch('extraartists')
#combined_names = "|".join(f'{ea["name"]}-{ea["role"]}' for ea in eas)
#print (f"cn={combined_names}")
#
#for ea in eas:
#    print(f"{ea['name']}-{ea['role']}")
