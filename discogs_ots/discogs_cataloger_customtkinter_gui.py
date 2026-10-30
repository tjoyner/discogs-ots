import sys
import shlex
import threading
import time
import customtkinter as ctk

MODE_FULL_COLLECTION = "Full Collection Query"
MODE_COLLECTION_SKIP_IDS = "Collection Query, Skip IDs in File"
MODE_COLLECTION_AFTER_DATE = "Collection Query, IDs added after date"
MODE_READ_IDS = "Read Release IDs from File"
MODE_SINGLE_ID = "Single Release ID"

# Attempt to import your existing script class safely
try:
    from discogs_ots import OtsDiscogsToCsv
except ImportError:
    # Dummy placeholder class if running gui.py standalone before integrating
    class OtsDiscogsToCsv:
        def __init__(self):
            self.stop_event = None

        def run(self):
            print("Starting Discogs processing run...")
            for i in range(1, 101):
                if self.stop_event and self.stop_event.is_set():
                    print("\n--> Interrupt signal detected inside processing loop!")
                    print("--> Halted execution safely.")
                    break
                print(f"Processing record item {i}/100...")
                time.sleep(0.6)

# Set global CustomTkinter dark theme defaults
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class TextRedirector:
    """Safely redirects stdout & stderr output into a CustomTkinter Textbox."""

    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        def _append():
            self.textbox.configure(state="normal")
            self.textbox.insert("end", text)
            self.textbox.see("end")
            self.textbox.configure(state="disabled")

        # Schedules UI update safely on main GUI thread
        self.textbox.after(0, _append)

    def flush(self):
        pass

    def reconfigure(self, *args, **kwargs):
        """Satisfies Python 3.8+ stream reconfigure calls."""
        pass

    def isatty(self):
        return False

    def readable(self):
        return False

    def writable(self):
        return True


class DiscogsCatalogerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Discogs Cataloger (OtsDiscogsToCsv)")
        self.geometry("780x680")
        self.minsize(680, 560)

        self.stop_event = threading.Event()
        self.worker_thread = None

        # --- Top Options Card ---
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(padx=20, pady=(20, 10), fill="x")

        # Download Mode Dropdown
        self.lbl_mode = ctk.CTkLabel(
            self.frame_top,
            text="Download Mode:",
            font=ctk.CTkFont(weight="bold"),
        )
        self.lbl_mode.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.combo_mode = ctk.CTkOptionMenu(
            self.frame_top,
            values=[
                MODE_FULL_COLLECTION,
                MODE_COLLECTION_SKIP_IDS,
                MODE_COLLECTION_AFTER_DATE,
                MODE_READ_IDS,
                MODE_SINGLE_ID,
            ],
            command=self.on_mode_change,
        )
        self.combo_mode.grid(
            row=0, column=1, padx=15, pady=(15, 5), sticky="ew"
        )

        # Config File Selection
        self.lbl_cfg = ctk.CTkLabel(
            self.frame_top, text="Config (.ini) File:", font=ctk.CTkFont(weight="bold")
        )
        self.lbl_cfg.grid(row=1, column=0, padx=15, pady=5, sticky="w")

        self.frame_cfg_input = ctk.CTkFrame(
            self.frame_top, fg_color="transparent"
        )
        self.frame_cfg_input.grid(row=1, column=1, padx=15, pady=5, sticky="ew")

        self.entry_cfg = ctk.CTkEntry(
            self.frame_cfg_input, placeholder_text=""
        )
        self.entry_cfg.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_cfg.insert(0, "my.ini")
        self.entry_cfg.bind(
            "<KeyRelease>", lambda e: self.update_cli_preview()
        )

        self.btn_browse = ctk.CTkButton(
            self.frame_cfg_input,
            text="Browse",
            width=70,
            command=self.browse_config,
        )
        self.btn_browse.pack(side="right")

        self.frame_top.grid_columnconfigure(1, weight=1)

        # --- Dynamic Input Container Frame ---
        self.frame_dynamic = ctk.CTkFrame(
            self.frame_top, fg_color="transparent"
        )
        self.frame_dynamic.grid(
            row=2, column=0, columnspan=2, padx=15, pady=10, sticky="ew"
        )

        # Output & Options Switches Bar
        self.frame_switches = ctk.CTkFrame(
            self.frame_top, fg_color="transparent"
        )
        self.frame_switches.grid(
            row=3, column=0, columnspan=5, padx=15, pady=(0, 15), sticky="ew"
        )

        self.switch_mrk = ctk.CTkSwitch(
            self.frame_switches,
            text="Generate .mrk File",
            command=self.update_cli_preview,
        )
        self.switch_mrk.grid(row=3, column=0, padx=20, pady=20)
        #button.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        self.switch_mrk.select()

        # Output directory
        # Label
        self.label = ctk.CTkLabel(self.frame_switches, text="Output Directory:")
        self.label.grid(row=3, column=3, padx=10, pady=20)

        # Entry box to display chosen path
        self.entry_dir = ctk.CTkEntry(
            self.frame_switches, width=280, placeholder_text="No directory selected"
        )
        self.entry_dir.grid(row=3, column=4, padx=5, pady=20)
        self.entry_dir.bind("<KeyRelease>", lambda e: self.update_cli_preview())

        # Browse Button
        self.btn_browse = ctk.CTkButton(
            self.frame_switches, text="Browse...", width=90, command=self.browse_directory
        )
        self.btn_browse.grid(row=3, column=5, padx=10, pady=20)

        # Label
        self.lbl_out = ctk.CTkLabel(self.frame_switches, text="Output CSV:")
        self.lbl_out.grid(row=3, column=1, padx=10, pady=5)

        self.entry_out = ctk.CTkEntry(self.frame_switches, width=160)
        self.entry_out.grid(row=3, column=2, padx=20, pady=20)
        self.entry_out.insert(0, "catalog_output.csv")
        self.entry_out.bind("<KeyRelease>", lambda e: self.update_cli_preview())
        

        # --- Generated Command Preview Card ---
        self.frame_cmd = ctk.CTkFrame(self)
        self.frame_cmd.pack(padx=20, pady=5, fill="x")

        self.lbl_cmd = ctk.CTkLabel(
            self.frame_cmd,
            text="Generated Command String Preview:",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        self.lbl_cmd.pack(anchor="w", padx=12, pady=(8, 2))

        self.entry_cmd = ctk.CTkEntry(
            self.frame_cmd,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="transparent",
            border_width=0,
            text_color="#1f6aa5",
        )
        self.entry_cmd.pack(fill="x", padx=12, pady=(0, 8))

        # --- Start / Interrupt Controls ---
        self.frame_controls = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_controls.pack(padx=20, pady=5, fill="x")

        self.btn_start = ctk.CTkButton(
            self.frame_controls,
            text="Start Download",
            fg_color="#2fa572",
            hover_color="#1f704c",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            command=self.start_thread,
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_stop = ctk.CTkButton(
            self.frame_controls,
            text="Interrupt / Stop",
            fg_color="#d9534f",
            hover_color="#b52b27",
            height=40,
            font=ctk.CTkFont(weight="bold"),
            state="disabled",
            command=self.interrupt_process,
        )
        self.btn_stop.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # --- Log Output Console ---
        self.txt_log = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
            wrap="word",
        )
        self.txt_log.pack(padx=20, pady=(10, 20), fill="both", expand=True)

        # Redirect standard output streams to GUI log
        sys.stdout = TextRedirector(self.txt_log)
        sys.stderr = TextRedirector(self.txt_log)

        # Initialize layout with default option
        self.on_mode_change(self.combo_mode.get())

    def browse_config(self):
        """File dialog to choose .ini config file."""
        filename = ctk.filedialog.askopenfilename(
            filetypes=[("INI Files", "*.ini"), ("All Files", "*.*")]
        )
        if filename:
            self.entry_cfg.delete(0, "end")
            self.entry_cfg.insert(0, filename)
            self.update_cli_preview()

    def browse_directory(self):
        # Opens native folder selection dialog
        selected_dir = ctk.filedialog.askdirectory(
            title="Select Output Folder", initialdir="."
        )

        # Update entry box if user chose a path (didn't cancel)
        if selected_dir:
            self.entry_dir.delete(0, "end")
            self.entry_dir.insert(0, selected_dir)
            self.update_cli_preview()

    def on_mode_change(self, selected_mode):
        """Rebuilds input parameter widgets dynamically based on dropdown selection."""
        for widget in self.frame_dynamic.winfo_children():
            widget.destroy()

        if selected_mode == MODE_SINGLE_ID:
            lbl = ctk.CTkLabel(
                self.frame_dynamic,
                text="Release ID:",
                font=ctk.CTkFont(weight="bold"),
            )
            lbl.pack(side="left", padx=(0, 10))

            self.release_id = ctk.CTkEntry(
                self.frame_dynamic, placeholder_text="e.g. 2491204", width=220
            )
            self.release_id.pack(side="left")
            self.release_id.insert(0, "2491204")
            self.release_id.bind(
                "<KeyRelease>", lambda e: self.update_cli_preview()
            )

        elif selected_mode == MODE_FULL_COLLECTION:
            pass

        elif selected_mode == MODE_COLLECTION_AFTER_DATE:
            lbl1 = ctk.CTkLabel(
                self.frame_dynamic,
                text="Added On or After (YYYY-MM-DD):",
                font=ctk.CTkFont(weight="bold"),
            )
            lbl1.pack(side="left", padx=(0, 5))

            self.dyn_entry1 = ctk.CTkEntry(self.frame_dynamic, width=120)
            self.dyn_entry1.pack(side="left", padx=(0, 20))
            self.dyn_entry1.insert(0, "2026-01-01")
            self.dyn_entry1.bind(
                "<KeyRelease>", lambda e: self.update_cli_preview()
            )

        self.update_cli_preview()

    def update_cli_preview(self):
        """Constructs and displays the current CLI command line string."""
        mode = self.combo_mode.get()
        cfg = self.entry_cfg.get().strip()
        out_dir = self.entry_dir.get().strip()
        out = self.entry_out.get().strip()
        mrk = self.switch_mrk.get()

        parts = ["python discogs_ots.py"]

        if cfg:
            parts.append(f"--config \"{cfg}\"")

        if mode == MODE_SINGLE_ID:
            val = getattr(self, "release_id", None)
            if val and val.get().strip():
                parts.append(f"--release-id {val.get().strip()}")

        elif mode == MODE_FULL_COLLECTION:
            parts.append("--query-for-ids")
            dt = getattr(self, "dyn_entry1", None)
            min_id = getattr(self, "dyn_entry2", None)
            if dt and dt.get().strip():
                parts.append(f"--added-after {dt.get().strip()}")

        elif mode == MODE_COLLECTION_SKIP_IDS:
            start_id = getattr(self, "dyn_entry1", None)
            end_id = getattr(self, "dyn_entry2", None)
            if (
                start_id
                and end_id
                and start_id.get().strip()
                and end_id.get().strip()
            ):
                parts.append(
                    f"--id-range {start_id.get().strip()}-{end_id.get().strip()}"
                )

        if mrk:
            parts.append("--write-mrk")

        if out:
            print (f"tom: {out_dir}")
            if out_dir:
                out = f"{out_dir}/{out}"
            parts.append(f"-o {out}")

        cmd_str = " ".join(parts)

        # Update preview entry box
        self.entry_cmd.configure(state="normal")
        self.entry_cmd.delete(0, "end")
        self.entry_cmd.insert(0, cmd_str)
        self.entry_cmd.configure(state="readonly")

    def start_thread(self):
        """Starts processing task inside a separate background thread."""
        cmd = self.entry_cmd.get()
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        # Parse generated CLI string into sys.argv list
        sys.argv = ["discogs_ots.py"] + shlex.split(
            cmd.replace("python discogs_ots.py ", "")
        )

        print(f"Executing: {' '.join(sys.argv)}\n" + "=" * 55)

        self.worker_thread = threading.Thread(
            target=self.run_process, daemon=True
        )
        self.worker_thread.start()

    def interrupt_process(self):
        """Signals background thread to stop immediately."""
        print(
            "\n[Interrupt Signal Sent] Stopping processing loop at next iteration..."
        )
        self.stop_event.set()
        self.btn_stop.configure(state="disabled")

    def run_process(self):
        """Instantiates and executes main script in background thread."""
        try:
            app = OtsDiscogsToCsv()
            app.stop_event = self.stop_event
            app.run()
            print("\n" + "=" * 55 + "\nProcessing run complete.")
        except Exception as e:
            print(f"\n[Error Encountered]: {e}")
        finally:
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")


if __name__ == "__main__":
    app = DiscogsCatalogerGUI()
    app.mainloop()
