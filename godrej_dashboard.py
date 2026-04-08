import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import math
import re
import io
from datetime import datetime, timedelta

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(
    page_title="Godrej Livestream Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #f8f9fc; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #1a1f36;
    }
    section[data-testid="stSidebar"] * {
        color: #e0e0e0 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stMultiSelect label,
    section[data-testid="stSidebar"] .stRadio label {
        color: #b0b8d1 !important;
        font-weight: 600;
    }
    
    /* KPI Cards */
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border-left: 4px solid #4361ee;
        margin-bottom: 8px;
    }
    .kpi-card h4 {
        color: #6c757d;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 8px 0;
    }
    .kpi-card .value {
        font-size: 28px;
        font-weight: 700;
        color: #1a1f36;
        margin: 0;
    }
    .kpi-card .delta {
        font-size: 13px;
        font-weight: 600;
        margin-top: 6px;
    }
    .delta-up { color: #10b981; }
    .delta-down { color: #ef4444; }
    .delta-neutral { color: #6b7280; }
    
    /* Section headers */
    .section-header {
        font-size: 20px;
        font-weight: 700;
        color: #1a1f36;
        margin: 32px 0 16px 0;
        padding-bottom: 8px;
        border-bottom: 2px solid #4361ee;
        display: inline-block;
    }
    
    /* Table styling */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .styled-table thead th {
        background: #1a237e;
        color: white;
        padding: 12px 16px;
        font-weight: 600;
        text-align: center;
    }
    .styled-table tbody td {
        padding: 10px 16px;
        text-align: center;
        border-bottom: 1px solid #eee;
    }
    .styled-table tbody tr:nth-child(even) { background: #f8f9fc; }
    .cell-green { background: #d1fae5 !important; color: #065f46; font-weight: 600; }
    .cell-red { background: #fee2e2 !important; color: #991b1b; font-weight: 600; }
    
    /* Funnel */
    .funnel-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 20px;
        flex-wrap: wrap;
    }
    
    /* Hide default streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 8px 8px 0 0;
        padding: 8px 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def format_val(v, fmt='gmv'):
    """Format: BIO / MIO / K with truncate"""
    if pd.isna(v) or v is None:
        return "0"
    if fmt == 'hour':
        return f"{v:.0f}"
    av = abs(v)
    sign = '' if v >= 0 else '-'
    if av >= 1_000_000_000:
        t = math.floor(av / 10_000_000) / 100
        return f"{sign}{t:.2f} BIO"
    if av >= 1_000_000:
        t = math.floor(av / 100_000) / 10
        return f"{sign}{t:.1f} MIO"
    if av >= 1_000:
        t = math.floor(av / 100) / 10
        return f"{sign}{t:.1f}K"
    return f"{v:,.0f}"


def pct_change(curr, prev):
    if prev == 0:
        return 0
    return (curr - prev) / prev * 100


def delta_html(val, suffix='%'):
    if val > 0:
        return f'<p class="delta delta-up">▲ +{val:.2f}{suffix}</p>'
    elif val < 0:
        return f'<p class="delta delta-down">▼ {val:.2f}{suffix}</p>'
    else:
        return f'<p class="delta delta-neutral">— 0{suffix}</p>'


def kpi_card(title, value, delta=None, border_color="#4361ee"):
    delta_str = ""
    if delta is not None:
        delta_str = delta_html(delta)
    return f"""
    <div class="kpi-card" style="border-left-color: {border_color};">
        <h4>{title}</h4>
        <p class="value">{value}</p>
        {delta_str}
    </div>
    """


BULAN_NAMES = {1:'Jan',2:'Feb',3:'Mar',4:'Apr',5:'May',6:'Jun',
               7:'Jul',8:'Aug',9:'Sep',10:'Oct',11:'Nov',12:'Dec'}


# ============================================================
# DATA LOADING
# ============================================================
@st.cache_data
def load_raw_data(file):
    df = pd.read_csv(file)
    for col in ['GMV', 'GMV (Placed Order)', 'Hour']:
        df[col] = df[col].astype(str).str.replace(',', '').str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
    df['Month'] = pd.to_numeric(df['Month'], errors='coerce')
    df['Session'] = df['Session'].astype(str).str.strip().str.upper()

    # Parse CO DATE SH to datetime
    df['Date'] = pd.to_datetime(df['CO DATE SH'], errors='coerce')

    # Parse Week
    df['Week'] = pd.to_numeric(df['Week'], errors='coerce')

    return df


@st.cache_data
def load_overview(file, fname):
    ov = pd.read_csv(file, header=1, thousands='.')
    row = ov.iloc[0]
    m_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', fname)
    if m_match:
        y, m = int(m_match.group(1)), int(m_match.group(2))
    else:
        y, m = 2026, 1
    return {
        'month': m, 'year': y,
        'label': BULAN_NAMES.get(m, str(m)),
        'views': float(row['Total Views']),
        'atc': float(row['Total ATC']),
        'orders': float(row['Orders(Confirmed Order)']),
        'likes': float(row['Total Likes']),
        'shares': float(row['Total Shares']),
        'comments': float(row['Total Comments']),
    }


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 📊 Godrej Analytics")
    st.markdown("---")

    st.markdown("### 📁 Upload Data")
    raw_file = st.file_uploader("Raw Data CSV", type=['csv'], key='raw',
                                 help="Upload Godrej_Data_-_Raw_Data-SH.csv")
    ov_files = st.file_uploader("Overview CSV (opsional)", type=['csv'],
                                 accept_multiple_files=True, key='overview',
                                 help="Upload overview-v2_1m_*.csv files")

if raw_file is None:
    st.markdown("""
    <div style="text-align:center; margin-top:100px;">
        <h1>📊 Godrej Livestream Analytics Dashboard</h1>
        <p style="font-size:18px; color:#6c757d;">Upload file <code>Godrej_Data_-_Raw_Data-SH.csv</code> di sidebar untuk memulai.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Load data
df = load_raw_data(raw_file)

# Load overview data
ov_data = []
if ov_files:
    for f in ov_files:
        d = load_overview(f, f.name)
        d['eng_rate'] = (d['likes'] + d['shares'] + d['comments']) / d['views'] * 100 if d['views'] > 0 else 0
        ov_data.append(d)
    ov_data.sort(key=lambda x: (x['year'], x['month']))

# ============================================================
# SIDEBAR FILTERS
# ============================================================
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🎯 Filter")

    available_years = sorted(df['Year'].dropna().unique().astype(int))
    selected_year = st.selectbox("Tahun", available_years, index=len(available_years)-1)

    view_mode = st.radio("Mode Tampilan", ["Bulanan", "Harian", "Mingguan", "Custom Range"],
                          horizontal=False)

    df_year = df[df['Year'] == selected_year].copy()

    if view_mode == "Bulanan":
        available_months = sorted(df_year['Month'].dropna().unique().astype(int))
        selected_months = st.multiselect(
            "Pilih Bulan", available_months,
            default=available_months[-3:] if len(available_months) >= 3 else available_months,
            format_func=lambda x: BULAN_NAMES.get(x, str(x))
        )
        if not selected_months:
            st.warning("Pilih minimal 1 bulan")
            st.stop()
        filtered = df_year[df_year['Month'].isin(selected_months)]
        group_col = 'Month'
        group_label_fn = lambda x: BULAN_NAMES.get(int(x), str(x))

    elif view_mode == "Harian":
        df_year_dated = df_year.dropna(subset=['Date'])
        if len(df_year_dated) == 0:
            st.error("Tidak ada data tanggal valid untuk tahun ini.")
            st.stop()
        min_date = df_year_dated['Date'].min().date()
        max_date = df_year_dated['Date'].max().date()
        date_range = st.date_input("Pilih Range Tanggal", value=(min_date, max_date),
                                     min_value=min_date, max_value=max_date)
        if len(date_range) == 2:
            filtered = df_year_dated[(df_year_dated['Date'].dt.date >= date_range[0]) &
                                     (df_year_dated['Date'].dt.date <= date_range[1])]
        else:
            filtered = df_year_dated[df_year_dated['Date'].dt.date == date_range[0]]
        group_col = 'Date'
        group_label_fn = lambda x: pd.Timestamp(x).strftime('%d %b')

    elif view_mode == "Mingguan":
        available_weeks = sorted(df_year['Week'].dropna().unique().astype(int))
        if not available_weeks:
            st.error("Data Week tidak tersedia.")
            st.stop()
        selected_weeks = st.multiselect(
            "Pilih Minggu", available_weeks,
            default=available_weeks[-4:] if len(available_weeks) >= 4 else available_weeks,
            format_func=lambda x: f"Week {x}"
        )
        if not selected_weeks:
            st.warning("Pilih minimal 1 minggu")
            st.stop()
        filtered = df_year[df_year['Week'].isin(selected_weeks)]
        group_col = 'Week'
        group_label_fn = lambda x: f"W{int(x)}"

    else:  # Custom Range
        available_months = sorted(df_year['Month'].dropna().unique().astype(int))
        col1, col2 = st.columns(2)
        with col1:
            m_start = st.selectbox("Dari Bulan", available_months,
                                     format_func=lambda x: BULAN_NAMES.get(x, str(x)))
        with col2:
            m_end = st.selectbox("Sampai Bulan", available_months,
                                   index=len(available_months)-1,
                                   format_func=lambda x: BULAN_NAMES.get(x, str(x)))
        selected_months = [m for m in available_months if m_start <= m <= m_end]
        filtered = df_year[df_year['Month'].isin(selected_months)]
        group_col = 'Month'
        group_label_fn = lambda x: BULAN_NAMES.get(int(x), str(x))

    # Session filter
    st.markdown("---")
    st.markdown("### 🏷️ Filter Session")
    all_sessions = sorted([str(s) for s in df['Session'].unique() if str(s).strip() not in ['NAN', '', 'NONE', 'nan', 'None']])
    selected_sessions = st.multiselect("Session", ['ALL'] + all_sessions, default=['ALL'])

    if 'ALL' not in selected_sessions and selected_sessions:
        filtered = filtered[filtered['Session'].isin(selected_sessions)]

    # Comparison toggle
    st.markdown("---")
    st.markdown("### 📊 Perbandingan")
    enable_comparison = st.checkbox("Aktifkan Perbandingan", value=False)
    comp_filtered = None

    if enable_comparison:
        comp_year = st.selectbox("Tahun Pembanding", available_years,
                                   index=max(0, len(available_years)-2), key='comp_year')
        df_comp_year = df[df['Year'] == comp_year].copy()

        if view_mode in ["Bulanan", "Custom Range"]:
            comp_months = st.multiselect(
                "Bulan Pembanding", sorted(df_comp_year['Month'].dropna().unique().astype(int)),
                default=selected_months if view_mode == "Bulanan" else [],
                format_func=lambda x: BULAN_NAMES.get(x, str(x)),
                key='comp_months'
            )
            comp_filtered = df_comp_year[df_comp_year['Month'].isin(comp_months)]
        elif view_mode == "Mingguan":
            comp_weeks_avail = sorted(df_comp_year['Week'].dropna().unique().astype(int))
            comp_weeks = st.multiselect("Minggu Pembanding", comp_weeks_avail,
                                          default=[], key='comp_weeks',
                                          format_func=lambda x: f"Week {x}")
            comp_filtered = df_comp_year[df_comp_year['Week'].isin(comp_weeks)]
        else:
            comp_filtered = None

        if 'ALL' not in selected_sessions and selected_sessions and comp_filtered is not None:
            comp_filtered = comp_filtered[comp_filtered['Session'].isin(selected_sessions)]


# ============================================================
# MAIN DASHBOARD
# ============================================================
st.markdown(f"""
<h1 style="color:#1a1f36; margin-bottom:0;">📊 Godrej Livestream Analytics</h1>
<p style="color:#6c757d; font-size:16px; margin-top:4px;">
    {selected_year} — {view_mode} View — {len(filtered)} livestreams
</p>
""", unsafe_allow_html=True)

# ============================================================
# KPI CARDS
# ============================================================
total_gmv = filtered['GMV'].sum()
total_hours = filtered['Hour'].sum()
avg_gmv_hour = total_gmv / total_hours if total_hours > 0 else 0
total_streams = len(filtered)

comp_delta_gmv = None
comp_delta_hours = None
comp_delta_avg = None
comp_delta_streams = None

if enable_comparison and comp_filtered is not None and len(comp_filtered) > 0:
    comp_gmv = comp_filtered['GMV'].sum()
    comp_hours = comp_filtered['Hour'].sum()
    comp_avg = comp_gmv / comp_hours if comp_hours > 0 else 0
    comp_delta_gmv = pct_change(total_gmv, comp_gmv)
    comp_delta_hours = pct_change(total_hours, comp_hours)
    comp_delta_avg = pct_change(avg_gmv_hour, comp_avg)
    comp_delta_streams = pct_change(total_streams, len(comp_filtered))

cols = st.columns(4)
with cols[0]:
    st.markdown(kpi_card("Total GMV", f"IDR {format_val(total_gmv)}",
                          comp_delta_gmv, "#4361ee"), unsafe_allow_html=True)
with cols[1]:
    st.markdown(kpi_card("Total Hours", format_val(total_hours, 'hour'),
                          comp_delta_hours, "#7c3aed"), unsafe_allow_html=True)
with cols[2]:
    st.markdown(kpi_card("AVG GMV/Hour", f"IDR {format_val(avg_gmv_hour)}",
                          comp_delta_avg, "#10b981"), unsafe_allow_html=True)
with cols[3]:
    st.markdown(kpi_card("Total Livestreams", f"{total_streams}",
                          comp_delta_streams, "#f59e0b"), unsafe_allow_html=True)


# ============================================================
# TABS
# ============================================================
tabs = st.tabs(["📈 GMV Analysis", "🏷️ Session (DD/PD)", "🔄 Conversion Funnel", "💬 Engagement", "📋 Raw Data"])


# ============================================================
# TAB 1: GMV ANALYSIS
# ============================================================
with tabs[0]:
    st.markdown('<p class="section-header">GMV Performance</p>', unsafe_allow_html=True)

    # Group data
    if group_col == 'Date':
        grouped = filtered.groupby(filtered['Date'].dt.date).agg(
            Hour=('Hour', 'sum'), GMV=('GMV', 'sum'), Count=('GMV', 'count')
        ).reset_index()
        grouped.columns = ['Period', 'Hour', 'GMV', 'Count']
        grouped['Label'] = grouped['Period'].apply(lambda x: x.strftime('%d %b'))
    else:
        grouped = filtered.groupby(group_col).agg(
            Hour=('Hour', 'sum'), GMV=('GMV', 'sum'), Count=('GMV', 'count')
        ).reset_index()
        grouped.columns = ['Period', 'Hour', 'GMV', 'Count']
        grouped['Label'] = grouped['Period'].apply(group_label_fn)

    grouped['GMV/Hour'] = grouped.apply(lambda r: r['GMV'] / r['Hour'] if r['Hour'] > 0 else 0, axis=1)
    grouped = grouped.sort_values('Period')

    # Chart: GMV bars + GMV/Hour line
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=grouped['Label'], y=grouped['GMV'] / 1e6,
               name='GMV (MIO)', marker_color='#4361ee',
               text=[format_val(v) for v in grouped['GMV']],
               textposition='outside', textfont=dict(size=11, color='#4361ee')),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=grouped['Label'], y=grouped['GMV/Hour'] / 1e6,
                   name='AVG GMV/Hour (MIO)', line=dict(color='#ef4444', width=3),
                   mode='lines+markers+text',
                   text=[f"{v/1e6:.1f}" for v in grouped['GMV/Hour']],
                   textposition='top center', textfont=dict(size=10, color='#ef4444')),
        secondary_y=True
    )

    # Comparison overlay
    if enable_comparison and comp_filtered is not None and len(comp_filtered) > 0:
        if group_col == 'Date':
            comp_grouped = comp_filtered.groupby(comp_filtered['Date'].dt.date).agg(
                GMV=('GMV', 'sum')).reset_index()
            comp_grouped['Label'] = comp_grouped['Date'].apply(lambda x: x.strftime('%d %b'))
        else:
            comp_grouped = comp_filtered.groupby(group_col).agg(GMV=('GMV', 'sum')).reset_index()
            comp_grouped['Label'] = comp_grouped[group_col].apply(group_label_fn)

        fig.add_trace(
            go.Bar(x=comp_grouped['Label'], y=comp_grouped['GMV'] / 1e6,
                   name=f'GMV Comparison ({comp_year})', marker_color='rgba(67,97,238,0.25)',
                   text=[format_val(v) for v in comp_grouped['GMV']],
                   textposition='outside', textfont=dict(size=9, color='#999')),
            secondary_y=False
        )

    fig.update_layout(
        height=450, barmode='group',
        plot_bgcolor='white', paper_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        margin=dict(t=60, b=40),
        yaxis_title='GMV (MIO)', yaxis2_title='AVG GMV/Hour (MIO)'
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
    st.plotly_chart(fig, use_container_width=True)

    # Summary Table
    st.markdown('<p class="section-header">Detail Table</p>', unsafe_allow_html=True)

    table_data = []
    for _, row in grouped.iterrows():
        table_data.append({
            'Period': row['Label'],
            'Hour': f"{row['Hour']:.0f}",
            'GMV': format_val(row['GMV']),
            'AVG GMV/Hour': format_val(row['GMV/Hour']),
            'Livestreams': f"{row['Count']:.0f}"
        })
    # Total row
    table_data.append({
        'Period': 'TOTAL',
        'Hour': f"{grouped['Hour'].sum():.0f}",
        'GMV': format_val(grouped['GMV'].sum()),
        'AVG GMV/Hour': format_val(grouped['GMV'].sum() / grouped['Hour'].sum() if grouped['Hour'].sum() > 0 else 0),
        'Livestreams': f"{grouped['Count'].sum():.0f}"
    })

    # MoM changes
    if len(grouped) > 1:
        mom_data = []
        for i in range(1, len(grouped)):
            prev = grouped.iloc[i-1]
            curr = grouped.iloc[i]
            mom_data.append({
                'Period': f"{group_label_fn(prev['Period'])} vs {group_label_fn(curr['Period'])}",
                'Hour': f"{pct_change(curr['Hour'], prev['Hour']):+.2f}%",
                'GMV': f"{pct_change(curr['GMV'], prev['GMV']):+.2f}%",
                'AVG GMV/Hour': f"{pct_change(curr['GMV/Hour'], prev['GMV/Hour']):+.2f}%",
                'Livestreams': f"{pct_change(curr['Count'], prev['Count']):+.2f}%"
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        st.markdown("**Month over Month:**")
        st.dataframe(pd.DataFrame(mom_data), use_container_width=True, hide_index=True)
    else:
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)


# ============================================================
# TAB 2: SESSION ANALYSIS (DD / PD)
# ============================================================
with tabs[1]:
    st.markdown('<p class="section-header">Session Performance: Double Date & Pay Day</p>', unsafe_allow_html=True)

    for session_code, session_name, color in [('DD', 'Double Date', '#4361ee'), ('PD', 'Pay Day', '#7c3aed')]:
        sf = filtered[filtered['Session'] == session_code]

        if len(sf) == 0:
            st.info(f"Tidak ada data {session_name} ({session_code}) untuk filter ini.")
            continue

        st.markdown(f"### {session_name} ({session_code})")

        # Group
        if group_col == 'Date':
            sg = sf.groupby(sf['Date'].dt.date).agg(Hour=('Hour','sum'), GMV=('GMV','sum')).reset_index()
            sg.columns = ['Period','Hour','GMV']
            sg['Label'] = sg['Period'].apply(lambda x: x.strftime('%d %b'))
        else:
            sg = sf.groupby(group_col).agg(Hour=('Hour','sum'), GMV=('GMV','sum')).reset_index()
            sg.columns = ['Period','Hour','GMV']
            sg['Label'] = sg['Period'].apply(group_label_fn)

        sg['GMV/Hour'] = sg.apply(lambda r: r['GMV']/r['Hour'] if r['Hour']>0 else 0, axis=1)
        sg = sg.sort_values('Period')

        # KPI
        s_gmv = sg['GMV'].sum()
        s_hours = sg['Hour'].sum()
        s_avg = s_gmv / s_hours if s_hours > 0 else 0

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(kpi_card("GMV", f"IDR {format_val(s_gmv)}", border_color=color), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card("Hours", format_val(s_hours, 'hour'), border_color=color), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi_card("AVG GMV/Hour", f"IDR {format_val(s_avg)}", border_color=color), unsafe_allow_html=True)

        # Chart
        fig_s = make_subplots(specs=[[{"secondary_y": True}]])
        fig_s.add_trace(
            go.Bar(x=sg['Label'], y=sg['GMV']/1e6, name='GMV (MIO)',
                   marker_color=color, text=[f"{v/1e6:.1f}" for v in sg['GMV']],
                   textposition='outside'),
            secondary_y=False
        )
        fig_s.add_trace(
            go.Scatter(x=sg['Label'], y=sg['GMV/Hour']/1e6, name='AVG GMV/Hour',
                       line=dict(color='#ef4444', width=2.5), mode='lines+markers+text',
                       text=[f"{v/1e6:.1f}" for v in sg['GMV/Hour']],
                       textposition='top center', textfont=dict(size=10, color='#ef4444')),
            secondary_y=True
        )
        fig_s.update_layout(
            height=380, plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(t=50, b=30),
            yaxis_title='GMV (MIO)', yaxis2_title='AVG GMV/Hour (MIO)'
        )
        fig_s.update_xaxes(showgrid=False)
        fig_s.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
        st.plotly_chart(fig_s, use_container_width=True)

        # Table
        tbl_data = []
        for _, r in sg.iterrows():
            tbl_data.append({
                'Period': r['Label'], 'Duration(Hour)': f"{r['Hour']:.0f}",
                'GMV': format_val(r['GMV']), 'Avg GMV/Hour': format_val(r['GMV/Hour'])
            })
        tbl_data.append({
            'Period': 'TOTAL', 'Duration(Hour)': f"{s_hours:.0f}",
            'GMV': format_val(s_gmv), 'Avg GMV/Hour': format_val(s_avg)
        })
        st.dataframe(pd.DataFrame(tbl_data), use_container_width=True, hide_index=True)

        st.markdown("---")


# ============================================================
# TAB 3: CONVERSION FUNNEL
# ============================================================
with tabs[2]:
    st.markdown('<p class="section-header">Conversion Funnel</p>', unsafe_allow_html=True)

    if not ov_data:
        st.info("Upload file Overview CSV di sidebar untuk melihat Conversion Funnel.")
    else:
        cols_f = st.columns(len(ov_data))

        for idx, (col, d) in enumerate(zip(cols_f, ov_data)):
            with col:
                views, atc, orders = d['views'], d['atc'], d['orders']
                atc_rate = atc / views * 100 if views > 0 else 0
                ord_rate_v = orders / views * 100 if views > 0 else 0
                ord_rate_a = orders / atc * 100 if atc > 0 else 0

                st.markdown(f"### {d['label']} {d['year']}")

                # Funnel using plotly
                fig_funnel = go.Figure(go.Funnel(
                    y=['Views', 'ATC', 'Orders'],
                    x=[views, atc, orders],
                    textinfo="value+percent previous",
                    texttemplate="%{x:,.0f}<br>(%{percentPrevious:.2%})",
                    marker=dict(color=['#6b7280', '#9ca3af', '#d1d5db']),
                    connector=dict(line=dict(color='#e5e7eb', width=1))
                ))
                fig_funnel.update_layout(
                    height=320, margin=dict(t=10, b=10, l=10, r=10),
                    plot_bgcolor='white', paper_bgcolor='white',
                    font=dict(size=12)
                )
                st.plotly_chart(fig_funnel, use_container_width=True)

                # Rates
                st.markdown(f"""
                | Metric | Rate |
                |--------|------|
                | ATC / Views | **{atc_rate:.2f}%** |
                | Orders / Views | **{ord_rate_v:.2f}%** |
                | Orders / ATC | **{ord_rate_a:.2f}%** |
                """)

        # Summary comparison table
        if len(ov_data) > 1:
            st.markdown("---")
            st.markdown('<p class="section-header">Funnel Comparison</p>', unsafe_allow_html=True)

            funnel_table = []
            for d in ov_data:
                atc_r = d['atc']/d['views']*100 if d['views']>0 else 0
                ord_v = d['orders']/d['views']*100 if d['views']>0 else 0
                ord_a = d['orders']/d['atc']*100 if d['atc']>0 else 0
                funnel_table.append({
                    'Period': f"{d['label']} {d['year']}",
                    'Views': format_val(d['views']),
                    'ATC': format_val(d['atc']),
                    'Orders': format_val(d['orders']),
                    'ATC/Views': f"{atc_r:.2f}%",
                    'Orders/Views': f"{ord_v:.2f}%",
                    'Orders/ATC': f"{ord_a:.2f}%"
                })
            # Total
            tv = sum(d['views'] for d in ov_data)
            ta = sum(d['atc'] for d in ov_data)
            to = sum(d['orders'] for d in ov_data)
            funnel_table.append({
                'Period': 'TOTAL',
                'Views': format_val(tv), 'ATC': format_val(ta), 'Orders': format_val(to),
                'ATC/Views': f"{ta/tv*100:.2f}%" if tv>0 else "0%",
                'Orders/Views': f"{to/tv*100:.2f}%" if tv>0 else "0%",
                'Orders/ATC': f"{to/ta*100:.2f}%" if ta>0 else "0%"
            })
            st.dataframe(pd.DataFrame(funnel_table), use_container_width=True, hide_index=True)


# ============================================================
# TAB 4: ENGAGEMENT
# ============================================================
with tabs[3]:
    st.markdown('<p class="section-header">Engagement Metrics</p>', unsafe_allow_html=True)

    if not ov_data:
        st.info("Upload file Overview CSV di sidebar untuk melihat Engagement data.")
    else:
        # Engagement KPIs
        total_views = sum(d['views'] for d in ov_data)
        total_likes = sum(d['likes'] for d in ov_data)
        total_shares = sum(d['shares'] for d in ov_data)
        total_comments = sum(d['comments'] for d in ov_data)
        total_eng_rate = (total_likes + total_shares + total_comments) / total_views * 100 if total_views > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(kpi_card("👁 Views", format_val(total_views), border_color="#6366f1"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card("👍 Likes", format_val(total_likes), border_color="#ec4899"), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi_card("↗ Shares", format_val(total_shares), border_color="#14b8a6"), unsafe_allow_html=True)
        with c4:
            st.markdown(kpi_card("💬 Comments", format_val(total_comments), border_color="#f97316"), unsafe_allow_html=True)
        with c5:
            st.markdown(kpi_card("📊 Eng. Rate", f"{total_eng_rate:.2f}%", border_color="#8b5cf6"), unsafe_allow_html=True)

        # Engagement Table
        eng_table = []
        for d in ov_data:
            eng_table.append({
                'Period': f"{d['label']} {d['year']}",
                '👁 Views': format_val(d['views']),
                '👍 Likes': format_val(d['likes']),
                '↗ Shares': format_val(d['shares']),
                '💬 Comments': format_val(d['comments']),
                'Eng. Rate': f"{d['eng_rate']:.2f}%"
            })
        eng_table.append({
            'Period': 'TOTAL',
            '👁 Views': format_val(total_views),
            '👍 Likes': format_val(total_likes),
            '↗ Shares': format_val(total_shares),
            '💬 Comments': format_val(total_comments),
            'Eng. Rate': f"{total_eng_rate:.2f}%"
        })
        st.dataframe(pd.DataFrame(eng_table), use_container_width=True, hide_index=True)

        # MoM
        if len(ov_data) > 1:
            st.markdown("**Month over Month:**")
            mom_eng = []
            for i in range(1, len(ov_data)):
                p, c = ov_data[i-1], ov_data[i]
                mom_eng.append({
                    'Comparison': f"{p['label']} vs {c['label']}",
                    'Views': f"{pct_change(c['views'], p['views']):+.2f}%",
                    'Likes': f"{pct_change(c['likes'], p['likes']):+.2f}%",
                    'Shares': f"{pct_change(c['shares'], p['shares']):+.2f}%",
                    'Comments': f"{pct_change(c['comments'], p['comments']):+.2f}%",
                    'Eng. Rate': f"{pct_change(c['eng_rate'], p['eng_rate']):+.2f}%"
                })
            st.dataframe(pd.DataFrame(mom_eng), use_container_width=True, hide_index=True)

        # Engagement Rate Chart
        st.markdown('<p class="section-header">Engagement Rate Trend</p>', unsafe_allow_html=True)
        labels_c = [f"{d['label']} {d['year']}" for d in ov_data]
        eng_rates = [d['eng_rate'] for d in ov_data]

        fig_eng = go.Figure()
        fig_eng.add_trace(go.Scatter(
            x=labels_c, y=eng_rates,
            mode='lines+markers+text',
            line=dict(color='#6366f1', width=3),
            marker=dict(size=10, color='#6366f1'),
            text=[f"{v:.2f}%" for v in eng_rates],
            textposition='top center',
            textfont=dict(size=12, color='#6366f1')
        ))
        fig_eng.update_layout(
            height=400, plot_bgcolor='white', paper_bgcolor='white',
            yaxis_title='Engagement Rate (%)',
            yaxis=dict(ticksuffix='%'),
            margin=dict(t=30, b=40)
        )
        fig_eng.update_xaxes(showgrid=False)
        fig_eng.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
        st.plotly_chart(fig_eng, use_container_width=True)

        # Breakdown chart: Likes, Shares, Comments stacked
        st.markdown('<p class="section-header">Engagement Breakdown</p>', unsafe_allow_html=True)
        fig_break = go.Figure()
        fig_break.add_trace(go.Bar(
            x=labels_c, y=[d['likes'] for d in ov_data],
            name='Likes', marker_color='#ec4899'
        ))
        fig_break.add_trace(go.Bar(
            x=labels_c, y=[d['comments'] for d in ov_data],
            name='Comments', marker_color='#f97316'
        ))
        fig_break.add_trace(go.Bar(
            x=labels_c, y=[d['shares'] for d in ov_data],
            name='Shares', marker_color='#14b8a6'
        ))
        fig_break.update_layout(
            barmode='stack', height=400,
            plot_bgcolor='white', paper_bgcolor='white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(t=50, b=40)
        )
        fig_break.update_xaxes(showgrid=False)
        fig_break.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
        st.plotly_chart(fig_break, use_container_width=True)


# ============================================================
# TAB 5: RAW DATA
# ============================================================
with tabs[4]:
    st.markdown('<p class="section-header">Raw Data Explorer</p>', unsafe_allow_html=True)

    st.markdown(f"**{len(filtered)} records** sesuai filter")

    display_cols = ['Date', 'Livestream Name', 'Session', 'Hour', 'GMV', 'GMV (Placed Order)',
                    'Viewers', 'Orders', 'Items Sold (Confirmed Order)']
    available_display = [c for c in display_cols if c in filtered.columns]

    st.dataframe(
        filtered[available_display].sort_values('Date', ascending=False) if 'Date' in available_display else filtered[available_display],
        use_container_width=True,
        hide_index=True,
        height=500
    )

    # Download button
    csv = filtered.to_csv(index=False)
    st.download_button(
        label="📥 Download Filtered Data (CSV)",
        data=csv,
        file_name=f"godrej_filtered_{selected_year}.csv",
        mime="text/csv"
    )
