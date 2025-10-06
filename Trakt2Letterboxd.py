import json
import csv
import os
import tkinter as tk
from tkinter import filedialog, messagebox

CHUNK_SIZE = 1000  # max rows per CSV


# --------------------------
# Load movies (watched + rated)
# --------------------------
def load_movies(json_path):
    """Load all movies from a Trakt JSON export (rated or watched)."""
    with open(json_path, "r", encoding="utf8") as f:
        data = json.load(f)

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
    """Merge new_movies into existing list, updating Rating/WatchedDate if needed."""
    movie_map = {(m["Title"], m["Year"]): m for m in existing}

    for m in new_movies:
        key = (m["Title"], m["Year"])
        if key in movie_map:
            if not movie_map[key]["Rating"] and m["Rating"]:
                movie_map[key]["Rating"] = m["Rating"]
            if not movie_map[key]["WatchedDate"] and m["WatchedDate"]:
                movie_map[key]["WatchedDate"] = m["WatchedDate"]
        else:
            movie_map[key] = m

    return list(movie_map.values())


# --------------------------
# Load watchlist
# --------------------------
def load_watchlist(json_path):
    """Load Trakt watchlist JSON and format for Letterboxd."""
    with open(json_path, "r", encoding="utf8") as f:
        data = json.load(f)

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
def run_gui():
    root = tk.Tk()
    root.withdraw()

    # ----------------
    # Section 1: Watched + Rated
    # ----------------
    messagebox.showinfo("Select Files", "Select Trakt JSON files for Watched + Rated movies")
    watched_files = filedialog.askopenfilenames(
        title="Select Watched + Rated JSON files",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    all_movies = []
    base_dir = os.path.dirname(watched_files[0]) if watched_files else "."

    for fpath in watched_files:
        data = load_movies(fpath)
        all_movies = merge_movies(all_movies, data)

    write_csv_chunks(all_movies, base_dir, "Ready-Letterboxd-movies")

    # ----------------
    # Section 2: Watchlist
    # ----------------
    messagebox.showinfo("Select Files", "Select Trakt JSON files for Watchlist")
    watchlist_files = filedialog.askopenfilenames(
        title="Select Watchlist JSON files",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )

    all_watchlist = []
    for fpath in watchlist_files:
        data = load_watchlist(fpath)
        all_watchlist.extend(data)

    # Force proper Letterboxd column order
    watchlist_headers = ["Title", "Year", "imdbID", "tmdbID", "Notes", "ListedDate"]
    write_csv_chunks(all_watchlist, base_dir, "Ready-Letterboxd-watchlist", headers=watchlist_headers)

    # ----------------
    # Summary
    # ----------------
    total_movies = len(all_movies)
    total_rated = sum(1 for m in all_movies if m["Rating"] not in ("", None))
    total_watchlist = len(all_watchlist)

    summary_msg = (
        f"✅ Export complete!\n\n"
        f"Watched + Rated movies: {total_movies}\n"
        f"Movies with ratings: {total_rated}\n"
        f"Movies without ratings: {total_movies - total_rated}\n\n"
        f"Watchlist movies: {total_watchlist}\n\n"
        f"Note: Watchlist CSV will not mark movies as watched."
    )

    messagebox.showinfo("Export Summary", summary_msg)


# --------------------------
# Entry point
# --------------------------
if __name__ == "__main__":
    run_gui()
