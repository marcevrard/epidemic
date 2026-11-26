# France Epidemic Surveillance Dashboard (Flu & COVID-19)

Automated epidemiological surveillance dashboard tracking weekly **Influenza (Grippe)** and **COVID-19** activity across Metropolitan France. The pipeline fetches daily data updates, archives CSV snapshots, and builds a self-contained interactive Plotly visualization deployed to GitHub Pages.

**Live Dashboard:** [https://marcevrard.github.io/epidemic](https://marcevrard.github.io/epidemic)

---

## Visualization Components

1. **Regional Choropleth Map (Latest Available Week):**
   * Displays emergency department visit rates per 100,000 inhabitants across the 13 Metropolitan French regions (INSEE codes `11`–`94`).
   * Includes an interactive toggle to switch between **Grippe (Flu)** and **COVID-19**, with regional SOS Médecins consultation rates displayed on hover.
2. **National Weekly Time Series (Trailing 5 Years):**
   * Plots weekly national emergency department visit rates per 100,000 for both pathogens over a rolling 5-year window.
   * Includes interactive range selectors (`6M`, `1Y`, `3Y`, `5Y`), a range slider, and legend toggles for national SOS Médecins consultation rates.

---

## Data Sources

* **Epidemiological Surveillance:** [Santé publique France — Odissé](https://odisse.santepubliquefrance.fr/) (SurSaUD® syndromic surveillance system, all-ages aggregate `Tous âges`):
  * `grippe-passages-urgences-et-actes-sos-medecin_reg` (Regional flu)
  * `grippe-passages-aux-urgences-et-actes-sos-medecins-france` (National flu)
  * `covid-19-passages-aux-urgences-et-actes-sos-medecins-region` (Regional COVID-19)
  * `covid-19-passages-aux-urgences-et-actes-sos-medecins-france` (National COVID-19)
* **Geographic Boundaries:** [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson) (`regions-version-simplifiee.geojson`).

---

## Repository Structure

```text
epidemic/
├── .github/
│   └── workflows/
│       └── deploy.yml              # Daily scheduled build and GitHub Pages deployment
├── .python-version                 # Pinned Python version (3.15)
├── data/                           # Versioned daily CSV snapshots
├── src/
│   └── epidemic/
│       ├── __init__.py
│       └── build_dashboard.py      # Data ingestion, normalization, and Plotly HTML generator
├── pyproject.toml                  # Project metadata, dependencies, and CLI entry point
├── uv.lock                         # Deterministic dependency lockfile
└── README.md
```

---

## Local Setup and Execution

This project uses [`uv`](https://docs.astral.sh/uv/) for Python version management (`Python 3.15`) and deterministic dependency resolution.

### 1. Install Dependencies

```bash
git clone [https://github.com/marcevrard/epidemic.git](https://github.com/marcevrard/epidemic.git)
cd epidemic
uv sync
```

### 2. Build the Dashboard

Run the registered console entry point to fetch the latest datasets, update `data/*.csv`, and generate `_site/index.html`:

```bash
uv run build-dashboard
```

Open `_site/index.html` in a browser to inspect the generated dashboard locally.

### 3. Optional Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GITHUB_DATA_BASE_URL` | Raw base URL of an upstream GitHub directory containing `flu_reg.csv`, `flu_nat.csv`, `covid_reg.csv`, and `covid_nat.csv`. When unset, data is fetched directly from Odissé. | `""` (Odissé API) |

---

## Automated Deployment (GitHub Actions)

The workflow in `.github/workflows/deploy.yml` automates daily updates and static site publication:

* **Schedule:** Runs daily at `06:00 UTC` (`cron: "0 6 * * *"`), on pushes to `main`, and on manual `workflow_dispatch` triggers.
* **Execution:** Installs exact dependencies via `uv sync --locked --no-dev`, executes `uv run build-dashboard`, commits updated snapshots in `data/` back to the repository, and publishes `_site/` via `actions/deploy-pages`.

### Initial Repository Configuration

To enable deployment on a fresh fork or clone:
1. Navigate to **Settings $\rightarrow$ Pages** in the GitHub repository.
2. Under **Build and deployment $\rightarrow$ Source**, select **GitHub Actions**.
3. Ensure workflow permissions under **Settings $\rightarrow$ Actions $\rightarrow$ General** allow read and write access (`contents: write`) so daily CSV snapshots can be committed to `data/`.