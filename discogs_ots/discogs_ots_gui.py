import sys
import shlex
import threading
import time
import customtkinter as ctk

# Attempt to import your existing script class safely
try:
    from discogs_ots import OtsDiscogsToCsv
except ImportError:
    # Fallback dummy class if discogs_ots.py is missing from working directory
    class OtsDiscogsToCsv:
        def __init__(self):
            self.stop_event = None

        def run(self):
            print("Starting Discogs processing run...")
            for i in range(1, 101):
                # Check for user interrupt signal
                if self.stop_event and self.stop_event.is_set():
                    print("--> Interrupt detected inside OtsDiscogsToCsv loop!")
                    break
                print(f"Processing collection record {i}/100...")
                time.sleep(0.8)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TextRedirector:
    """Safely redirects stdout & stderr output into the CustomTkinter Textbox."""
    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        def _append():
            self.textbox.configure(state="normal")
            self.textbox.insert("end", text)
            self.textbox.see("end")
            self.textbox.configure(state="disabled")

        # Schedule Tkinter UI update safely on the main thread
        self.textbox.after(0, _append)

    def flush(self):
        pass

    def reconfigure(self, *args, **kwargs):
        """Satisfies Python 3.7+ stream calls."""
        pass

    def isatty(self):
        return False


class DiscogsCatalogerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Configuration ---
        self.title("Discogs Cataloger (OtsDiscogsToCsv)")
        self.geometry("750x600")
        self.minsize(620, 480)

        # Threading signals
        self.stop_event = threading.Event()
        self.worker_thread = None

        # --- Top Frame: Command Line Input ---
        self.frame_cli = ctk.CTkFrame(self)
        self.frame_cli.pack(padx=20, pady=(20, 10), fill="x")

        self.lbl_cli = ctk.CTkLabel(
            self.frame_cli, 
            text="Command Line Input Arguments:", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_cli.pack(anchor="w", padx=15, pady=(12, 6))

        # Raw CLI Command Entry
        self.entry_cli = ctk.CTkEntry(
            self.frame_cli, 
            placeholder_text="e.g. --config my.ini --query-for-ids -o output.csv --write-mrk",
            font=ctk.CTkFont(family="Consolas", size=12),
            height=35
        )
        self.entry_cli.pack(padx=15, pady=(0, 10), fill="x")
        self.entry_cli.insert(0, "--config my.ini --query-for-ids -o output.csv --write-mrk")

        # --- Quick Add Tag Helper Buttons ---
        self.frame_tags = ctk.CTkFrame(self.frame_cli, fg_color="transparent")
        self.frame_tags.pack(padx=15, pady=(0, 12), fill="x")

        self.lbl_tags = ctk.CTkLabel(
            self.frame_tags, 
            text="Quick Flags:", 
            font=ctk.CTkFont(size=11), 
            text_color="gray"
        )
        self.lbl_tags.pack(side="left", padx=(0, 8))

        quick_flags = [
            ("--query-for-ids", "--query-for-ids"),
            ("--write-mrk", "--write-mrk"),
            ("--added-after", "--added-after 2026-01-01"),
            ("--min-release-id", "--min-release-id 25000000"),
            ("--config", "--config my.ini")
        ]

        for label, flag in quick_flags:
            btn = ctk.CTkButton(
                self.frame_tags, 
                text=f"+ {label}", 
                width=90, 
                height=26,
                font=ctk.CTkFont(size=11),
                command=lambda f=flag: self.append_flag(f)
            )
            btn.pack(side="left", padx=(0, 6))

        # --- Middle Frame: Control Buttons (Start / Stop) ---
        self.frame_controls = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_controls.pack(padx=20, pady=5, fill="x")

        self.btn_start = ctk.CTkButton(
            self.frame_controls, 
            text="Start Processing", 
            fg_color="#2fa572", 
            hover_color="#1f704c",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.start_thread
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_stop = ctk.CTkButton(
            self.frame_controls, 
            text="Stop / Interrupt", 
            fg_color="#d9534f", 
            hover_color="#b52b27",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self.interrupt_process
        )
        self.btn_stop.pack(side="right", expand=True, fill="x", padx=(6, 0))

        # --- Bottom Frame: Console Output Terminal ---
        self.lbl_log = ctk.CTkLabel(self, text="Real-Time Standard Output Console Log:")
        self.lbl_log.pack(padx=20, pady=(12, 2), anchor="w")

        self.txt_log = ctk.CTkTextbox(
            self, 
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            wrap="word"
        )
        self.txt_log.pack(padx=20, pady=(0, 20), fill="both", expand=True)

        # Redirect standard stdout and stderr to GUI console
        sys.stdout = TextRedirector(self.txt_log)
        sys.stderr = TextRedirector(self.txt_log)

    def append_flag(self, flag):
        """Appends quick flag parameter to command input line if not present."""
        current = self.entry_cli.get().strip()
        flag_base = flag.split()[0]
        if flag_base not in current:
            self.entry_cli.delete(0, "end")
            self.entry_cli.insert(0, f"{current} {flag}".strip())

    def start_thread(self):
        """Parses arguments and launches background worker thread."""
        cli_string = self.entry_cli.get().strip()
        if not cli_string:
            print("Error: Command line argument string is empty!\n")
            return

        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        # Tokenize user inputs safely into sys.argv
        sys.argv = ["discogs_ots.py"] + shlex.split(cli_string)
        print(f"Executing: {' '.join(sys.argv)}\n" + "="*50)

        # Spawn background processing thread
        self.worker_thread = threading.Thread(target=self.run_process, daemon=True)
        self.worker_thread.start()

    def interrupt_process(self):
        """Sends cancellation signal to background processing thread."""
        print("\n[Interrupt Requested] Halting process...")
        self.stop_event.set()
        self.btn_stop.configure(state="disabled")

    def run_process(self):
        """Executes main python script in thread and cleans up UI upon completion."""
        try:
            app = OtsDiscogsToCsv()
            app.stop_event = self.stop_event
            app.run()

            if self.stop_event.is_set():
                print("\n" + "="*50 + "\nExecution interrupted by user signal.")
            else:
                print("\n" + "="*50 + "\nProcessing completed successfully.")

        except Exception as e:
            print(f"\nExecution Error: {e}")
        finally:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")


if __name__ == "__main__":
    app = DiscogsCatalogerGUI()
    app.mainloop()