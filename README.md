# France Epidemic Surveillance Dashboard (Flu & COVID-19)

Automated epidemiological surveillance dashboard tracking weekly **Influenza (Grippe)** and **COVID-19** syndromic activity across Metropolitan France. The pipeline fetches daily updates, archives versioned CSV snapshots, and builds an interactive Plotly dashboard published to GitHub Pages.

**Live Dashboard:** [https://marcevrard.github.io/epidemic](https://marcevrard.github.io/epidemic)

---

## Visualization Components

1. **Regional Choropleth Map (Latest Available Week):**
   * Displays emergency department visit rates per 100,000 coded visits across the 13 Metropolitan French regions (INSEE codes `11`–`94`).
   * Includes an interactive toggle button to switch between **Grippe (Flu)** and **COVID-19**, with regional SOS Médecins consultation rates shown in hover tooltips.
2. **National Weekly Time Series (Trailing 5 Years):**
   * Plots weekly national emergency department visit rates per 100,000 for both pathogens over a rolling 5-year window.
   * Includes interactive range selectors (`6M`, `1Y`, `3Y`, `5Y`), a range slider, and legend toggles for national SOS Médecins consultation rates.

---

## Data Sources

* **Epidemiological Surveillance:** [Santé publique France — Odissé](https://odisse.santepubliquefrance.fr/) (SurSaUD® syndromic surveillance system, all-ages aggregate `Tous âges`):
  * `grippe-passages-urgences-et-actes-sos-medecin_reg` (Regional flu: `taux_passages_grippe_sau`, `taux_actes_grippe_sos`)
  * `grippe-passages-aux-urgences-et-actes-sos-medecins-france` (National flu)
  * `covid-19-passages-aux-urgences-et-actes-sos-medecins-region` (Regional COVID-19: `taux_passages_covid_sau`, `taux_actes_covid_sos`)
  * `covid-19-passages-aux-urgences-et-actes-sos-medecins-france` (National COVID-19)
* **Geographic Boundaries:** [gregoiredavid/france-geojson](https://github.com/gregoiredavid/france-geojson) (`regions-version-simplifiee.geojson`).

---

## Repository Structure

```text
epidemic/
├── .github/
│   ├── dependabot.yml                      # Weekly Dependabot updates (GitHub Actions & uv)
│   └── workflows/
│       ├── ci.yaml                         # PR lockfile & dashboard build check (verify-build)
│       ├── dependabot-auto-merge.yaml      # Auto-approve & squash-merge Dependabot PRs
│       └── deploy.yaml                     # Daily cron: update data/*.csv & deploy Pages
├── .gitignore                              # Excludes .venv/, _site/, and Python caches
├── .python-version                         # Pinned Python version (3.15)
├── README.md                               # Project overview, data sources & setup guide
├── data/                                   # Tracked daily epidemiological CSV snapshots
│   ├── covid_nat.csv
│   ├── covid_reg.csv
│   ├── flu_nat.csv
│   └── flu_reg.csv
├── pyproject.toml                          # Project metadata, dependencies & build-dashboard CLI
├── src/
│   └── epidemic/
│       ├── __init__.py
│       └── build_dashboard.py              # Odissé ingestion, normalization & Plotly HTML export
└── uv.lock                                 # Deterministic dependency lockfile
```

---

## Local Setup and Testing

This project uses [`uv`](https://docs.astral.sh/uv/) for Python version management (`Python 3.15`) and deterministic dependency resolution.

### 1. Install Dependencies

```bash
git clone [https://github.com/marcevrard/epidemic.git](https://github.com/marcevrard/epidemic.git)
cd epidemic
uv sync
```

### 2. Build and Preview the Dashboard Locally

Run the console entry point to fetch the latest datasets, update `data/*.csv`, and generate `_site/index.html`:

```bash
uv run build-dashboard
uv run python -m http.server 8000 --directory _site
```

Open `http://localhost:8000` in a browser to inspect the generated dashboard.

### 3. Validate GitHub Actions Workflows Locally

```bash
uvx actionlint-py
```

### 4. Optional Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GITHUB_DATA_BASE_URL` | Raw base URL of an upstream GitHub directory containing `flu_reg.csv`, `flu_nat.csv`, `covid_reg.csv`, and `covid_nat.csv`. When unset, data is fetched directly from Odissé. | `""` (Odissé API) |

---

## CI/CD and Automated Maintenance

* **Daily Data Sync & Pages Deployment (`.github/workflows/deploy.yaml`):**
  * Runs daily at `06:00 UTC` (`cron: "0 6 * * *"`), on pushes to `main`, and via manual `workflow_dispatch`.
  * Job `update-data` fetches fresh CSV exports, commits changes in `data/*.csv` with rebase-retry handling, and pushes to `main`.
  * Job `deploy-pages` checks out the updated branch tip, builds `_site/index.html`, verifies that `_site/index.html` is non-empty, and publishes to GitHub Pages.
* **Pull Request Verification (`.github/workflows/ci.yaml`):**
  * Runs `uv sync --locked` and `uv run build-dashboard` on pull requests targeting `main` (`verify-build` status check).
* **Automated Dependency Updates (`.github/dependabot.yml` & `.github/workflows/dependabot-auto-merge.yaml`):**
  * Checks weekly (Mondays at `07:00 Europe/Paris`) for `github-actions` and grouped `uv` Python package updates, automatically approving and squash-merging Dependabot PRs once `verify-build` passes.

### Required Repository Settings

1. **GitHub Pages (`Settings → Pages`):** Set **Build and deployment → Source** to **GitHub Actions**.
2. **Workflow Permissions (`Settings → Actions → General`):** Select **Read and write permissions** and enable **Allow GitHub Actions to create and approve pull requests**.
3. **Auto-Merge (`Settings → General → Pull Requests`):** Enable **Allow auto-merge**.
4. **Branch Protection (`Settings → Branches` or `Rulesets`):** Protect `main` and require the **`verify-build`** status check to pass before merging.