import json
import csv
import os
import re
import tempfile
import threading
import zipfile
import platform
import ctypes
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, ttk
import webbrowser

CHUNK_SIZE = 1000  # max rows per CSV


# --------------------------
# Load movies (watched + rated)
# --------------------------
def load_movies(json_path):
    """Load all movies from a Trakt JSON export (rated or watched)."""
    data = load_json_entries(json_path)

    movies = []
    for entry in data:
        movie = entry.get("movie")
        if not movie:
            continue

        ids = movie.get("ids", {})

        watched_date = entry.get("last_watched_at") or entry.get("watched_at") or entry.get("rated_at") or ""
        rating = entry.get("rating")
        if rating is not None:
            try:
                rating = float(rating) / 2
            except Exception:
                rating = ""

        movies.append({
            "WatchedDate": watched_date,
            "Rating": rating if rating is not None else "",
            "tmdbID": ids.get("tmdb", ""),
            "imdbID": ids.get("imdb", ""),
            "Title": movie.get("title", ""),
            "Year": movie.get("year", ""),
        })

    return movies


# --------------------------
# Merge movies (deduplicate)
# --------------------------
def merge_movies(existing, new_movies):
    """Merge new_movies into existing list, preferring IMDb ID and falling back to Title/Year."""
    imdb_map = {}
    title_year_map = {}
    merged = []

    def add_or_merge(movie):
        imdb_id = movie.get("imdbID", "") or ""
        title_year_key = (movie.get("Title", ""), movie.get("Year", ""))

        existing_movie = None
        if imdb_id:
            existing_movie = imdb_map.get(imdb_id)
            if existing_movie is None:
                title_movie = title_year_map.get(title_year_key)
                if title_movie and not title_movie.get("imdbID"):
                    existing_movie = title_movie
                    existing_movie["imdbID"] = imdb_id
                    imdb_map[imdb_id] = existing_movie
        else:
            existing_movie = title_year_map.get(title_year_key)

        if existing_movie is None:
            existing_movie = {
                "WatchedDate": movie.get("WatchedDate", ""),
                "Rating": movie.get("Rating", ""),
                "tmdbID": movie.get("tmdbID", ""),
                "imdbID": imdb_id,
                "Title": movie.get("Title", ""),
                "Year": movie.get("Year", ""),
            }
            merged.append(existing_movie)
            title_year_map[title_year_key] = existing_movie
            if imdb_id:
                imdb_map[imdb_id] = existing_movie
            return

        if not existing_movie.get("Rating") and movie.get("Rating"):
            existing_movie["Rating"] = movie["Rating"]
        if not existing_movie.get("WatchedDate") and movie.get("WatchedDate"):
            existing_movie["WatchedDate"] = movie["WatchedDate"]
        if not existing_movie.get("tmdbID") and movie.get("tmdbID"):
            existing_movie["tmdbID"] = movie["tmdbID"]
        if not existing_movie.get("imdbID") and imdb_id:
            existing_movie["imdbID"] = imdb_id
            imdb_map[imdb_id] = existing_movie

    for movie in existing:
        add_or_merge(movie)

    for movie in new_movies:
        add_or_merge(movie)

    return merged


# --------------------------
# Load watchlist
# --------------------------
def load_watchlist(json_path):
    """Load Trakt watchlist JSON and format for Letterboxd."""
    data = load_json_entries(json_path)

    watchlist = []
    for entry in data:
        if entry.get("type") != "movie":
            continue
        movie = entry.get("movie")
        if not movie:
            continue

        watchlist.append({
            "Title": movie.get("title", ""),
            "Year": movie.get("year", ""),
            "imdbID": movie.get("ids", {}).get("imdb", ""),
            "tmdbID": movie.get("ids", {}).get("tmdb", ""),
            "Notes": entry.get("notes") or "",
            "ListedDate": entry.get("listed_at", ""),
        })
    return watchlist


# --------------------------
# ZIP export discovery

def find_export_files(base_dir):
    """Discover Trakt exported files inside an extracted ZIP export."""
    watched_files = []
    rating_files = []
    watchlist_files = []

    for root, _, files in os.walk(base_dir):
        for filename in files:
            lower_name = filename.lower()
            if lower_name.startswith("watched-movies") and lower_name.endswith(".json"):
                watched_files.append(os.path.join(root, filename))
            elif lower_name.startswith("ratings-movies") and lower_name.endswith(".json"):
                rating_files.append(os.path.join(root, filename))
            elif lower_name.startswith("lists-watchlist") and lower_name.endswith(".json"):
                watchlist_files.append(os.path.join(root, filename))

    watched_files.sort(key=lambda path: natural_sort_key(os.path.basename(path)))
    rating_files.sort(key=lambda path: natural_sort_key(os.path.basename(path)))
    watchlist_files.sort(key=lambda path: natural_sort_key(os.path.basename(path)))
    return watched_files, rating_files, watchlist_files


def natural_sort_key(value):
    """Return a key suitable for natural numeric sorting."""
    parts = re.split(r"(\d+)", value)
    return [int(part) if part.isdigit() else part.lower() for part in parts]


def load_json_entries(json_path):
    """Load a Trakt JSON file and return the top-level entry array."""
    with open(json_path, "r", encoding="utf8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("data", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    raise ValueError(
        "Expected JSON root to be a list or an object containing 'data' or 'items' arrays."
    )


def extract_export_zip(zip_path):
    """Extract a Trakt export ZIP into a temporary directory."""
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("The selected file is not a valid ZIP archive.")

    temp_dir = tempfile.TemporaryDirectory()
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(temp_dir.name)

    return temp_dir


# --------------------------
# Write CSV chunks
# --------------------------
def write_csv_chunks(data, base_path, prefix, headers=None):
    """Write a list of dicts to CSV files in chunks of CHUNK_SIZE."""
    if not data:
        print(f"⚠️ No data to export for '{prefix}'")
        return

    total = len(data)
    num_files = (total + CHUNK_SIZE - 1) // CHUNK_SIZE

    for i in range(num_files):
        chunk = data[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
        filename = f"{prefix}_{i+1}.csv" if num_files > 1 else f"{prefix}.csv"
        out_path = os.path.join(base_path, filename)

        with open(out_path, "w", encoding="utf8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers or list(chunk[0].keys()))
            writer.writeheader()
            writer.writerows(chunk)

        print(f"✅ Wrote {len(chunk)} entries → {out_path}")


# --------------------------
# Main GUI
# --------------------------
def enable_windows_dpi_awareness():
    if platform.system() != "Windows":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def center_window(root, width=520, height=320):
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = max((screen_width - width) // 2, 0)
    y = max((screen_height - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(width, height)


def run_gui():
    enable_windows_dpi_awareness()

    root = tk.Tk()
    root.title("Trakt2Letterboxd")
    root.configure(bg="#0a0a0a")
    root.geometry("550x665")
    root.minsize(550, 665)

    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(size=10)
    default_family = "Segoe UI" if platform.system() == "Windows" else default_font.actual("family")

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("TFrame", background="#0a0a0a")
    style.configure("Card.TFrame", background="#141414", borderwidth=0)
    style.configure("Header.TLabel", background="#0a0a0a", foreground="#ffffff", font=(default_family, 18, "bold"))
    style.configure("Subheader.TLabel", background="#0a0a0a", foreground="#9ca3af", font=(default_family, 10))
    style.configure("Accent.TButton", background="#ff003c", foreground="#ffffff", font=(default_family, 10, "bold"), padding=(12, 10))
    style.map(
        "Accent.TButton",
        background=[("active", "#e60036"), ("disabled", "#5c080f")],
        foreground=[("disabled", "#9ca3af")],
    )
    style.configure("Secondary.TButton", background="#1f1f1f", foreground="#ffffff", font=(default_family, 9, "bold"), padding=(10, 8))
    style.map(
        "Secondary.TButton",
        background=[("active", "#2e2e2e"), ("disabled", "#1f1f1f")],
    )
    style.configure("Path.TLabel", background="#0d0d0d", foreground="#f8fafc", font=(default_family, 9), relief="flat", padding=(10, 8))
    style.configure("Status.TLabel", background="#0a0a0a", foreground="#d1d5db", font=(default_family, 9))
    style.configure("ResultCard.TFrame", background="#141414", borderwidth=1, relief="solid")
    style.configure("ResultHeader.TLabel", background="#141414", foreground="#ffffff", font=(default_family, 11, "bold"))
    # Card-specific label styles (use only for the select label and status label)
    style.configure("SubheaderCard.TLabel", background="#141414", foreground="#9ca3af", font=(default_family, 10))
    style.configure("StatusCard.TLabel", background="#141414", foreground="#d1d5db", font=(default_family, 9))
    style.configure(
        "Dark.Vertical.TScrollbar",
        troughcolor="#0d0d0d",
        background="#1f1f1f",
        arrowcolor="#f8fafc",
        bordercolor="#0d0d0d",
        gripcount=0,
        relief="flat",
        troughrelief="flat",
    )
    style.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", "#2e2e2e"), ("disabled", "#1f1f1f")],
        troughcolor=[("active", "#0d0d0d")],
    )

    selected_zip = tk.StringVar(value="No file selected")
    status_var = tk.StringVar(value="Choose your Trakt export ZIP file to begin.")

    main_frame = ttk.Frame(root, padding=14, style="TFrame")
    main_frame.pack(fill="both", expand=True)
    main_frame.columnconfigure(0, weight=1)

    title_label = ttk.Label(main_frame, text="TRAKT ► LETTERBOXD", style="Header.TLabel")
    title_label.grid(column=0, row=0, sticky="w")

    subtitle_label = ttk.Label(main_frame, text="Transfer your Trakt watch history to Letterboxd", style="Subheader.TLabel")
    subtitle_label.grid(column=0, row=1, sticky="w", pady=(3, 3))

    card_frame = ttk.Frame(main_frame, padding=16, style="Card.TFrame")
    card_frame.grid(column=0, row=2, sticky="nsew")
    card_frame.columnconfigure(0, weight=1)
    card_frame.rowconfigure(4, weight=1)

    select_label = ttk.Label(card_frame, text="select the exported zip file =>", style="SubheaderCard.TLabel")
    select_label.grid(column=0, row=0, sticky="w")

    select_button = ttk.Button(card_frame, text="Browse ZIP", style="Secondary.TButton", command=lambda: select_zip())
    select_button.grid(column=1, row=0, sticky="e")

    file_label = ttk.Label(card_frame, textvariable=selected_zip, style="Path.TLabel", wraplength=520)
    file_label.grid(column=0, row=1, columnspan=2, sticky="ew", pady=(10, 14))

    convert_button = ttk.Button(card_frame, text="Convert", style="Accent.TButton", state="disabled", command=lambda: start_conversion())
    convert_button.grid(column=0, row=2, columnspan=2, sticky="ew")

    status_label = ttk.Label(card_frame, textvariable=status_var, style="StatusCard.TLabel")
    status_label.grid(column=0, row=3, columnspan=2, sticky="w", pady=(12, 8))

    style.configure("Accent.Horizontal.TProgressbar", troughcolor="#0d0d0d", background="#ff003c", bordercolor="#0f0f0f", lightcolor="#ff4b6a", darkcolor="#bf002f")
    progress_bar = ttk.Progressbar(card_frame, style="Accent.Horizontal.TProgressbar", mode="determinate", maximum=100, value=0)
    progress_bar.grid(column=0, row=5, columnspan=2, sticky="ew", pady=(0, 12))

    result_frame = ttk.Frame(card_frame, padding=14, style="ResultCard.TFrame")
    result_frame.grid(column=0, row=6, columnspan=2, sticky="nsew")
    result_frame.columnconfigure(0, weight=1)
    result_frame.rowconfigure(1, weight=1)

    result_title = ttk.Label(result_frame, text="Log", style="ResultHeader.TLabel")
    result_title.grid(column=0, row=0, sticky="w", pady=(0, 10))

    results_text = tk.Text(
        result_frame,
        bg="#0d0d0d",
        fg="#f8fafc",
        insertbackground="#ffffff",
        relief="flat",
        wrap="word",
        state="disabled",
        font=(default_family, 9),
        borderwidth=0,
        highlightthickness=0,
        padx=8,
        pady=8,
        height=8,
    )
    results_text.grid(column=0, row=1, sticky="nsew")

    scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=results_text.yview, style="Dark.Vertical.TScrollbar")
    scrollbar.grid(column=1, row=1, sticky="ns")
    results_text.configure(yscrollcommand=scrollbar.set)

    def set_status(text, level="normal"):
        color = "#9ca3af"
        if level == "success":
            color = "#7ee787"
        elif level == "error":
            color = "#ff6d77"
        elif level == "warning":
            color = "#fbbf24"
        status_label.config(foreground=color)
        status_var.set(text)

    def safe_update_status(text, level="normal"):
        # Use root.after to safely update UI from worker threads
        try:
            root.after(0, set_status, text, level)
        except Exception:
            # If root is not available, silently ignore
            pass

    def append_log(message, tag=None):
        results_text.config(state="normal")
        results_text.insert("end", message + "\n")
        if tag:
            start_index = f"end-{len(message)+1}c"
            results_text.tag_add(tag, start_index, "end-1c")
        results_text.see("end")
        results_text.config(state="disabled")

    results_text.tag_configure("info", foreground="#d1d5db")
    results_text.tag_configure("success", foreground="#7ee787")
    results_text.tag_configure("warning", foreground="#fbbf24")
    results_text.tag_configure("error", foreground="#ff6d77")
    results_text.tag_configure("summary", foreground="#ffffff")

    def clear_results():
        results_text.config(state="normal")
        results_text.delete("1.0", "end")
        results_text.config(state="disabled")

    def select_zip():
        zip_path = filedialog.askopenfilename(
            title="Select Trakt export ZIP file",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if not zip_path:
            return
        selected_zip.set(zip_path)
        convert_button.config(state="normal")
        set_status("Ready to convert.", "info")
        clear_results()
        append_log("ZIP selected. Press Convert to begin.", "info")

    def on_conversion_complete(summary_message):
        progress_bar.stop()
        progress_bar.config(mode="determinate", maximum=100)
        progress_bar['value'] = 100
        progress_bar.update_idletasks()
        convert_button.config(state="normal")
        select_button.config(state="normal")
        set_status("Conversion completed successfully.", "success")
        append_log("✅ Conversion complete.", "success")
        append_log(summary_message, "summary")
        convert_button.config(text="Convert Again")

    def on_conversion_error(error_message):
        progress_bar.stop()
        progress_bar.config(mode="determinate", maximum=100)
        progress_bar['value'] = 0
        progress_bar.update_idletasks()
        convert_button.config(state="normal")
        select_button.config(state="normal")
        set_status("Conversion failed. See activity below.", "error")
        append_log(f"❌ {error_message}", "error")
        convert_button.config(text="Retry")

    def start_conversion():
        convert_button.config(state="disabled")
        select_button.config(state="disabled")
        progress_bar.config(mode="indeterminate", value=0)
        progress_bar.start(10)
        clear_results()
        append_log("Starting conversion...", "info")
        set_status("Preparing conversion...", "info")

        def worker():
            zip_path = selected_zip.get()
            temp_dir = None
            skipped_files = []
            all_movies = []
            all_watchlist = []
            base_dir = os.path.dirname(zip_path) or "."
            try:
                root.after(0, lambda: append_log("Extracting ZIP archive...", "info"))
                safe_update_status("Extracting ZIP archive...")
                temp_dir = extract_export_zip(zip_path)

                root.after(0, lambda: append_log("Discovering export files...", "info"))
                safe_update_status("Discovering export files...")
                watched_files, rating_files, watchlist_files = find_export_files(temp_dir.name)
                if not watched_files and not rating_files:
                    raise ValueError(
                        "No watched or rated movie files were found in the selected Trakt ZIP export. "
                        "Please ensure the export contains files named starting with watched-movies or ratings-movies."
                    )

                for fpath in watched_files + rating_files:
                    root.after(0, lambda path=fpath: append_log(f"Loading {os.path.basename(path)}...", "info"))
                    safe_update_status(f"Loading {os.path.basename(fpath)}...")
                    try:
                        data = load_movies(fpath)
                    except Exception as exc:
                        skipped_files.append((fpath, str(exc)))
                        root.after(0, lambda path=fpath, exc=exc: append_log(f"Warning: Skipped {os.path.basename(path)} - {exc}", "warning"))
                        continue
                    all_movies = merge_movies(all_movies, data)

                root.after(0, lambda: append_log("Writing movie CSV file(s)...", "info"))
                safe_update_status("Writing movie CSV file(s)...")
                write_csv_chunks(all_movies, base_dir, "Ready-Letterboxd-movies")

                for fpath in watchlist_files:
                    root.after(0, lambda path=fpath: append_log(f"Loading watchlist {os.path.basename(path)}...", "info"))
                    safe_update_status(f"Loading watchlist {os.path.basename(fpath)}...")
                    try:
                        data = load_watchlist(fpath)
                    except Exception as exc:
                        skipped_files.append((fpath, str(exc)))
                        root.after(0, lambda path=fpath, exc=exc: append_log(f"Warning: Skipped {os.path.basename(path)} - {exc}", "warning"))
                        continue
                    all_watchlist.extend(data)

                root.after(0, lambda: append_log("Writing watchlist CSV file(s)...", "info"))
                safe_update_status("Writing watchlist CSV file(s)...")
                watchlist_headers = ["Title", "Year", "imdbID", "tmdbID", "Notes", "ListedDate"]
                write_csv_chunks(all_watchlist, base_dir, "Ready-Letterboxd-watchlist", headers=watchlist_headers)

                total_movies = len(all_movies)
                total_rated = sum(1 for m in all_movies if m["Rating"] not in ("", None))
                total_watchlist = len(all_watchlist)

                summary_msg = (
                    f"Export Summary:\n"
                    f"• Watched + Rated movies: {total_movies}\n"
                    f"• Movies with ratings: {total_rated}\n"
                    f"• Movies without ratings: {total_movies - total_rated}\n"
                    f"• Watchlist movies: {total_watchlist}\n"
                )
                if skipped_files:
                    summary_msg += "\nSkipped files:\n"
                    for path, error in skipped_files:
                        summary_msg += f"• {os.path.basename(path)}: {error}\n"

                root.after(0, on_conversion_complete, summary_msg)
            except Exception as exc:
                root.after(0, on_conversion_error, str(exc))
            finally:
                if temp_dir:
                    temp_dir.cleanup()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    # Source link section
    source_url = "https://github.com/ThePsychof/Trakt2Letterboxd"
    def open_source(event=None):
        try:
            webbrowser.open(source_url)
        except Exception:
            pass
    source_link = tk.Label(
        card_frame,
        text="Source",
        fg="#ff4d6d",
        bg="#141414",
        cursor="hand2",
        font=(default_family, 10, "bold")
    )
    source_link.grid(
        column=0,
        row=7,
        columnspan=2,
        pady=(16, 0)
    )
    source_link.bind("<Button-1>", open_source)
    source_link.bind(
        "<Enter>",
        lambda e: source_link.config(fg="#ff003c")
    )
    source_link.bind(
        "<Leave>",
        lambda e: source_link.config(fg="#ff4d6d")
    )
    #
    center_window(root, width=550, height=665)
    root.mainloop()
# --------------------------
# Entry point
# --------------------------
if __name__ == "__main__":
    run_gui()