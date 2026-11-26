import io
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GEOJSON_URL = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
    "master/regions-version-simplifiee.geojson"
)

# Optional: set this env var to a GitHub raw folder URL if you pull from an
# upstream GitHub data repo (e.g., https://raw.githubusercontent.com/user/repo/main/data)
GITHUB_DATA_BASE_URL = os.getenv("GITHUB_DATA_BASE_URL", "").rstrip("/")

# Santé publique France (Odissé) OpenDataSoft v2.1 CSV export endpoints
ODISSE_BASE = "https://odisse.santepubliquefrance.fr/api/explore/v2.1/catalog/datasets"
DATASETS = {
    "flu_reg": "grippe-passages-urgences-et-actes-sos-medecin_reg",
    "flu_nat": "grippe-passages-aux-urgences-et-actes-sos-medecins-france",
    "covid_reg": "covid-19-passages-aux-urgences-et-actes-sos-medecins-region",
    "covid_nat": "covid-19-passages-aux-urgences-et-actes-sos-medecins-france",
}

# Metropolitan France INSEE region codes matching france-geojson
METRO_REGIONS = {
    "11": "Île-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comté",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhône-Alpes",
    "93": "Provence-Alpes-Côte d'Azur",
    "94": "Corse",
}

DATA_DIR = Path("data")
SITE_DIR = Path("_site")


# ---------------------------------------------------------------------------
# Data Ingestion & Normalization
# ---------------------------------------------------------------------------
def fetch_csv(key: str) -> pd.DataFrame:
    """Download CSV from an upstream GitHub repo if configured, else Odissé."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    local_cache = DATA_DIR / f"{key}.csv"

    if GITHUB_DATA_BASE_URL:
        url = f"{GITHUB_DATA_BASE_URL}/{key}.csv"
        sep = ","
    else:
        slug = DATASETS[key]
        url = (
            f"{ODISSE_BASE}/{slug}/exports/csv"
            "?lang=fr&timezone=Europe%2FParis&use_labels=false&delimiter=%3B"
        )
        sep = ";"

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), sep=sep, low_memory=False)
    df.to_csv(local_cache, index=False)
    return df


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str:
    """Locate the first matching column name (case-insensitive substring match)."""
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand in cols_lower:
            return cols_lower[cand]
    for cand in candidates:
        for col_l, orig in cols_lower.items():
            if cand in col_l:
                return orig
    raise KeyError(f"None of {candidates} found in columns: {list(df.columns)}")


def normalize_surveillance_df(df: pd.DataFrame, is_regional: bool) -> pd.DataFrame:
    """Standardize date, age group ('Tous âges'), region code, and incidence rates."""
    date_col = _find_col(df, ["date_complet", "date_de_passage", "date", "semaine"])
    age_col = _find_col(
        df, ["sursaud_cl_age_gene", "sursaud_cl_age", "cl_age", "classe_d_age"]
    )
    er_col = _find_col(
        df,
        [
            "taux_passages_grippe_sau",
            "taux_passages_covid_sau",
            "taux_passages_urgences",
            "passages_urgences",
        ],
    )
    sos_col = _find_col(
        df,
        [
            "taux_actes_grippe_sos",
            "taux_actes_covid_sos",
            "taux_actes_sos",
            "actes_sos",
        ],
    )

    # Filter to all-ages aggregate ("Tous âges" or legacy code "0")
    age_series = df[age_col].astype(str).str.strip()
    df = df[age_series.isin(["0", "Tous âges", "tous ages"])].copy()

    # Parse ISO week or Monday date (date_complet)
    if (
        "semaine" in date_col.lower()
        and df[date_col].astype(str).str.contains("-S").any()
    ):
        df["week_date"] = pd.to_datetime(
            df[date_col].astype(str).str.replace("-S", "-W") + "-1",
            format="%G-W%V-%u",
            errors="coerce",
        )
        df["week_label"] = df[date_col].astype(str)
    else:
        df["week_date"] = pd.to_datetime(df[date_col], errors="coerce")
        iso = df["week_date"].dt.isocalendar()
        df["week_label"] = (
            iso["year"].astype(str) + "-S" + iso["week"].astype(str).str.zfill(2)
        )

    df["er_rate"] = pd.to_numeric(df[er_col], errors="coerce")
    df["sos_rate"] = pd.to_numeric(df[sos_col], errors="coerce")

    # Keep trailing 5 years
    cutoff = pd.Timestamp.now().normalize() - pd.DateOffset(years=5)
    df = df[df["week_date"] >= cutoff].dropna(subset=["week_date"])

    if is_regional:
        reg_col = _find_col(df, ["region", "code_region", "reg"])
        df["reg_code"] = (
            df[reg_col].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(2)
        )
        df = df[df["reg_code"].isin(METRO_REGIONS)].copy()
        df["reg_name"] = df["reg_code"].map(METRO_REGIONS)
        return (
            df[
                [
                    "week_date",
                    "week_label",
                    "reg_code",
                    "reg_name",
                    "er_rate",
                    "sos_rate",
                ]
            ]
            .sort_values(["week_date", "reg_code"])
            .drop_duplicates(subset=["week_date", "reg_code"], keep="last")
        )

    return (
        df[["week_date", "week_label", "er_rate", "sos_rate"]]
        .sort_values("week_date")
        .drop_duplicates(subset=["week_date"], keep="last")
    )


# ---------------------------------------------------------------------------
# Visualization (Plotly)
# ---------------------------------------------------------------------------
def build_figure(
    geojson: dict,
    flu_reg: pd.DataFrame,
    covid_reg: pd.DataFrame,
    flu_nat: pd.DataFrame,
    covid_nat: pd.DataFrame,
) -> go.Figure:
    """Create an interactive choropleth + 5-year weekly time-series figure."""
    latest_flu_week = flu_reg["week_date"].max()
    latest_covid_week = covid_reg["week_date"].max()

    flu_latest = flu_reg[flu_reg["week_date"] == latest_flu_week].copy()
    covid_latest = covid_reg[covid_reg["week_date"] == latest_covid_week].copy()

    flu_week_str = flu_latest["week_label"].iloc[0]
    covid_week_str = covid_latest["week_label"].iloc[0]

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.46, 0.54],
        specs=[[{"type": "choropleth"}, {"type": "xy"}]],
        subplot_titles=(
            f"Regional Emergency Visits ({flu_week_str})",
            "National Weekly Evolution — Last 5 Years (per 100,000)",
        ),
        horizontal_spacing=0.06,
    )

    # Trace 0: Regional Choropleth — Flu (initially visible)
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            locations=flu_latest["reg_code"],
            z=flu_latest["er_rate"],
            featureidkey="properties.code",
            colorscale="YlOrRd",
            colorbar=dict(
                title="ER / 100k",
                x=0.43,
                len=0.78,
                thickness=14,
            ),
            customdata=flu_latest[["reg_name", "sos_rate", "week_label"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[2]})<br>"
                "Flu ER visits: <b>%{z:.1f}</b> / 100k<br>"
                "Flu SOS Médecins: <b>%{customdata[1]:.1f}</b> / 100k"
                "<extra></extra>"
            ),
            name="Flu (Regional)",
            visible=True,
        ),
        row=1,
        col=1,
    )

    # Trace 1: Regional Choropleth — COVID-19 (toggled via button)
    fig.add_trace(
        go.Choropleth(
            geojson=geojson,
            locations=covid_latest["reg_code"],
            z=covid_latest["er_rate"],
            featureidkey="properties.code",
            colorscale="PuBuGn",
            colorbar=dict(
                title="ER / 100k",
                x=0.43,
                len=0.78,
                thickness=14,
            ),
            customdata=covid_latest[["reg_name", "sos_rate", "week_label"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[2]})<br>"
                "COVID-19 ER visits: <b>%{z:.1f}</b> / 100k<br>"
                "COVID-19 SOS Médecins: <b>%{customdata[1]:.1f}</b> / 100k"
                "<extra></extra>"
            ),
            name="COVID-19 (Regional)",
            visible=False,
        ),
        row=1,
        col=1,
    )

    # Trace 2: National Weekly Flu — Emergency Visits
    fig.add_trace(
        go.Scatter(
            x=flu_nat["week_date"],
            y=flu_nat["er_rate"],
            mode="lines",
            name="Flu — ER Visits (/100k)",
            line=dict(color="#d95f02", width=2.2),
            customdata=flu_nat["week_label"],
            hovertemplate="%{customdata} (%{x|%Y-%m-%d})<br>Flu ER: <b>%{y:.1f}</b> / 100k<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Trace 3: National Weekly COVID-19 — Emergency Visits
    fig.add_trace(
        go.Scatter(
            x=covid_nat["week_date"],
            y=covid_nat["er_rate"],
            mode="lines",
            name="COVID-19 — ER Visits (/100k)",
            line=dict(color="#1b9e77", width=2.2),
            customdata=covid_nat["week_label"],
            hovertemplate="%{customdata} (%{x|%Y-%m-%d})<br>COVID-19 ER: <b>%{y:.1f}</b> / 100k<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Trace 4 & 5: SOS Médecins rates (hidden by default in legend, clickable)
    fig.add_trace(
        go.Scatter(
            x=flu_nat["week_date"],
            y=flu_nat["sos_rate"],
            mode="lines",
            name="Flu — SOS Médecins (/100k)",
            line=dict(color="#d95f02", width=1.5, dash="dot"),
            visible="legendonly",
            customdata=flu_nat["week_label"],
            hovertemplate="%{customdata}<br>Flu SOS: <b>%{y:.1f}</b> / 100k<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Scatter(
            x=covid_nat["week_date"],
            y=covid_nat["sos_rate"],
            mode="lines",
            name="COVID-19 — SOS Médecins (/100k)",
            line=dict(color="#1b9e77", width=1.5, dash="dot"),
            visible="legendonly",
            customdata=covid_nat["week_label"],
            hovertemplate="%{customdata}<br>COVID-19 SOS: <b>%{y:.1f}</b> / 100k<extra></extra>",
        ),
        row=1,
        col=2,
    )

    # Map viewport framing Metropolitan France
    fig.update_geos(
        fitbounds="locations",
        visible=False,
        row=1,
        col=1,
    )

    # Interactive map switcher buttons (Flu vs. COVID-19)
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.02,
                y=1.13,
                xanchor="left",
                yanchor="top",
                bgcolor="#f1f5f9",
                bordercolor="#cbd5e1",
                buttons=[
                    dict(
                        label="Map: Grippe (Flu)",
                        method="update",
                        args=[
                            {
                                "visible": [
                                    True,
                                    False,
                                    True,
                                    True,
                                    "legendonly",
                                    "legendonly",
                                ]
                            },
                            {
                                "annotations[0].text": f"Regional Flu ER Visits ({flu_week_str})"
                            },
                        ],
                    ),
                    dict(
                        label="Map: COVID-19",
                        method="update",
                        args=[
                            {
                                "visible": [
                                    False,
                                    True,
                                    True,
                                    True,
                                    "legendonly",
                                    "legendonly",
                                ]
                            },
                            {
                                "annotations[0].text": f"Regional COVID-19 ER Visits ({covid_week_str})"
                            },
                        ],
                    ),
                ],
            )
        ],
        xaxis=dict(
            title="Week",
            rangeselector=dict(
                buttons=[
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(count=3, label="3Y", step="year", stepmode="backward"),
                    dict(step="all", label="5Y"),
                ]
            ),
            rangeslider=dict(visible=True, thickness=0.06),
            type="date",
        ),
        yaxis=dict(title="Rate per 100,000 coded visits/acts", rangemode="tozero"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="right", x=1.0),
        margin=dict(l=20, r=25, t=95, b=30),
        height=640,
        template="plotly_white",
    )

    return fig


def main() -> None:
    geojson = requests.get(GEOJSON_URL, timeout=60).json()

    flu_reg = normalize_surveillance_df(fetch_csv("flu_reg"), is_regional=True)
    covid_reg = normalize_surveillance_df(fetch_csv("covid_reg"), is_regional=True)
    flu_nat = normalize_surveillance_df(fetch_csv("flu_nat"), is_regional=False)
    covid_nat = normalize_surveillance_df(fetch_csv("covid_nat"), is_regional=False)

    fig = build_figure(geojson, flu_reg, covid_reg, flu_nat, covid_nat)
    plot_html = fig.to_html(full_html=False, include_plotlyjs="cdn")

    updated_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>France Epidemic Surveillance — Flu &amp; COVID-19</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 0 auto;
      max-width: 1400px;
      padding: 1.5rem 2rem;
      color: #1e293b;
      background: #ffffff;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 0.75rem;
      margin-bottom: 1rem;
    }}
    h1 {{ font-size: 1.35rem; margin: 0; }}
    .meta {{ font-size: 0.85rem; color: #64748b; }}
    footer {{
      margin-top: 1rem;
      font-size: 0.8rem;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Epidemic Surveillance in France: Grippe (Flu) &amp; COVID-19</h1>
    <span class="meta">Last updated: {updated_utc}</span>
  </header>
  {plot_html}
  <footer>
    Data: Santé publique France (SurSaUD® / Odissé) &bull;
    Boundaries: <a href="https://github.com/gregoiredavid/france-geojson">gregoiredavid/france-geojson</a>
  </footer>
</body>
</html>
"""

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(html_page, encoding="utf-8")


if __name__ == "__main__":
    main()
