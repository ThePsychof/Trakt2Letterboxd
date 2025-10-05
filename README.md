# 🎬 Trakt to Letterboxd CSV Exporter

Convert your exported **[Trakt](https://trakt.tv/)** data into CSV files that can be imported directly into **[Letterboxd](https://letterboxd.com/)**.

---

## ⚡ Features

- ✅ Export **watched movies** from your Trakt JSON exports  
- ⭐ Export **rated movies** (if available) from Trakt  
- 📋 Export **watchlist movies** from Trakt  
- 🗂 Separate CSV files for **watched/rated** and **watchlist**  
- 🔄 Deduplicates movies and merges ratings automatically  
- 🧩 Large exports are split into **chunks of 1000 rows** for Letterboxd compatibility  

---

## 🚀 Usage

1. Ensure you have **Python 3.x** installed on your system.  
2. Run the script:

```bash
python Trakt2Letterboxd.py
