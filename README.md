# 🎬 Trakt to Letterboxd CSV Exporter

Convert your exported **[Trakt](https://trakt.tv/)** data into CSV files that can be imported directly into [Letterboxd](https://letterboxd.com/).

---

## ⚡ Features

- ✅ Export **watched movies** from your Trakt JSON exports
- ⭐ Export **rated movies** from your Trakt JSON exports
- 📋 Export **watchlist movies** from your Trakt JSON exports
- 🗂 Generate separate CSV files for watched/rated and watchlist
- 🔄 Automatically deduplicate movies and merge ratings
- 🧩 Split large exports into 1,000-row chunks for Letterboxd compatibility
- 🖥 Standalone Windows executable available — no Python installation required
- ⚡ Fast, lightweight and completely offline

---

##  📥 Download
Download the latest Windows executable from the [Releases](https://github.com/ThePsychof/Trakt2Letterboxd/releases/tag/v1.0.0) page.
No installation required—just download and run.

---

## 🚀 Windows Usage

1. Download **Trakt2Letterboxd.exe** from the latest GitHub Release.
2. Run the executable.
3. Select your exported Trakt ZIP file.
4. The generated CSV files will be saved in the same address and are ready to import into Letterboxd.

---

## 🐍 Running from Source

If you prefer using Python:

1. Install Python 3.x.
2. Clone this repository
3. Run:

```bash
python Trakt2Letterboxd.py
```

---

## 📥 Exporting Your Trakt Data

1. Log in to [Trakt](https://trakt.tv).
2. Go to Settings → Data → Export Data.
3. Download your export ZIP file.
4. Use that ZIP file as the input for this application.

---

## 📄 Output

The program generates Letterboxd-compatible CSV files for:

- 🎬⭐ Ready-Letterboxd-movies (containing both movies and ratings)
- 📋 Ready-Letterboxd-watchlist (containing watchlist list)

Large exports are automatically split into multiple CSV files when needed.

---

## 📜 License

See the repository's [LICENSE](https://github.com/ThePsychof/Trakt2Letterboxd/blob/main/LICENSE) file for licensing information.
