# Godrej Livestream Analytics Dashboard

## Cara Install & Jalankan

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Jalankan dashboard
streamlit run godrej_dashboard.py
```

## File yang Dibutuhkan
- `Godrej_Data_-_Raw_Data-SH.csv` — data utama (wajib)
- `overview-v2_1m_*.csv` — data overview per bulan (opsional, untuk Funnel & Engagement)

## Fitur
- **Filter Fleksibel**: Harian, Mingguan, Bulanan, Custom Range
- **Perbandingan Periode**: Bandingkan 2 periode berbeda
- **Filter Session**: ALL, BAU, DD, PD, PW
- **5 Tab Analisis**:
  1. GMV Analysis — chart + table + MoM
  2. Session DD/PD — KPI + chart + table per session
  3. Conversion Funnel — Views → ATC → Orders
  4. Engagement — Views, Likes, Shares, Comments, Eng. Rate
  5. Raw Data Explorer — lihat & download data mentah
