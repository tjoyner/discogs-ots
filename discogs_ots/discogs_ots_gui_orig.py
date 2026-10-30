import threading
import sys
import customtkinter as ctk
from pathlib import Path

# Import your existing class from discogs_ots.py
from discogs_ots import OtsDiscogsToCsv

ctk.set_appearance_mode("System")  # Uses OS theme (Dark/Light)
ctk.set_default_color_theme("blue")


class TextRedirector:
    """Redirects print statements and log writes into the GUI Textbox safely."""

    def __init__(self, textbox):
        self.textbox = textbox

    def write(self, text):
        # Ensure UI updates happen safely
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def flush(self):
        pass

    def reconfigure(self, *args, **kwargs):
        """Dummy method to satisfy Python standard library stream calls."""
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

        self.title("Discogs Cataloger")
        self.geometry("650x550")

        # --- Options Frame ---
        self.frame_options = ctk.CTkFrame(self)
        self.frame_options.pack(padx=20, pady=10, fill="x")

        # Single Release ID Entry
        self.lbl_id = ctk.CTkLabel(self.frame_options, text="Single Release ID:")
        self.lbl_id.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.entry_id = ctk.CTkEntry(self.frame_options, placeholder_text="e.g. 123456")
        self.entry_id.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Config File Selection
        self.lbl_cfg = ctk.CTkLabel(self.frame_options, text="Config File:")
        self.lbl_cfg.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_cfg = ctk.CTkEntry(self.frame_options, placeholder_text="my.ini")
        self.entry_cfg.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.btn_browse = ctk.CTkButton(self.frame_options, text="Browse", width=80, command=self.browse_config)
        self.btn_browse.grid(row=1, column=2, padx=10, pady=10)

        # Switches / Checkboxes
        self.switch_mrk = ctk.CTkSwitch(self.frame_options, text="Generate .mrk File")
        self.switch_mrk.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        self.switch_mrk.select()

        self.switch_qi = ctk.CTkSwitch(self.frame_options, text="Query Full Collection (--query-for-ids)")
        self.switch_qi.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # --- Run Button ---
        self.btn_run = ctk.CTkButton(self, text="Start Processing", command=self.start_thread, fg_color="green")
        self.btn_run.pack(padx=20, pady=10, fill="x")

        # --- Log Console View ---
        self.lbl_log = ctk.CTkLabel(self, text="Console / Operation Log:")
        self.lbl_log.pack(padx=20, pady=(10, 0), anchor="w")
        
        self.txt_log = ctk.CTkTextbox(self, state="disabled")
        self.txt_log.pack(padx=20, pady=10, fill="both", expand=True)

        # Redirect standard output to textbox
        sys.stdout = TextRedirector(self.txt_log)

    def browse_config(self):
        filename = ctk.filedialog.askopenfilename(filetypes=[("INI Files", "*.ini"), ("All Files", "*.*")])
        if filename:
            self.entry_cfg.delete(0, "end")
            self.entry_cfg.insert(0, filename)

    def start_thread(self):
        """Runs the script in a separate thread so GUI doesn't freeze."""
        self.btn_run.configure(state="disabled", text="Processing...")
        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        try:
            # Build CLI args dynamically based on GUI fields
            sys.argv = ["discogs_ots.py"]
            
            cfg = self.entry_cfg.get().strip()
            if cfg:
                sys.argv.extend(["--config", cfg])

            rel_id = self.entry_id.get().strip()
            if rel_id:
                sys.argv.extend(["--release-id", rel_id])

            if self.switch_mrk.get():
                sys.argv.append("--write-mrk")

            if self.switch_qi.get():
                sys.argv.append("--query-for-ids")

            print(f"Executing: {' '.join(sys.argv)}\n" + "-"*40)

            # Instantiates and executes your existing script logic
            app = OtsDiscogsToCsv()
            app.run()
            
            print("\n" + "="*40 + "\nProcessing Complete!")
        except Exception as e:
            print(f"\nError encountered: {e}")
        finally:
            self.btn_run.configure(state="normal", text="Start Processing")


if __name__ == "__main__":
    app = DiscogsCatalogerGUI()
    app.mainloop()
