# Prompt2Data — Synthetic Data Generator Agent

> **Turn any subject into a realistic, analysis-ready dataset in seconds.**

Prompt2Data is a **custom agent** that generates comprehensive synthetic datasets from a plain-English description. It creates a dedicated project folder containing a fully-executed Jupyter notebook with data generation code, visualizations, statistical summaries, and a clean CSV export — all in one command.

---

## Benefits

| Benefit | Details |
|---|---|
| **Zero boilerplate** | Describe what you need; the agent scaffolds the entire notebook, installs packages, and runs every cell for you. |
| **Realistic data** | Produces domain-aware values with proper distributions, correlations, outliers, and business rules — not random junk. |
| **Instant analysis** | Every run includes multiple matplotlib/seaborn visualizations, summary statistics, and automated validation checks. |
| **Reproducible** | Seeded random generation, parameterized functions, and a self-contained project folder make results reproducible and shareable. |
| **Flexible** | Works for any domain — HR analytics, weather, retail sales, scientific measurements, social behavior — just change the subject line. |
| **Time-saving** | Eliminates the repetitive work of setting up environments, writing boilerplate generation code, and creating charts. |
| **Safe by design** | Generates fully synthetic data with no real PII, helping teams prototype dashboards and models without touching sensitive production data. |

---

## How to Use

### Prerequisites

- [VS Code](https://code.visualstudio.com/) with the **GitHub Copilot** and **GitHub Copilot Chat** extensions installed
- A Python environment with `pip` available (the agent installs required packages automatically)

### Step 1 — Invoke the Agent

Open the Copilot Chat panel and type:

```text
@workspace /prompt2data HR people analytics for org and worksite insights
```

or use the slash-command shortcut if configured:

```text
/prompt2data weather for 12 states for 12 months
```

### Step 2 — Wait for Execution

The agent will:

1. Parse your subject into a clean folder/file name
2. Create a dedicated project folder
3. Set up the Python environment and install dependencies
4. Create a Jupyter notebook with structured cells
5. **Execute every cell** — catching errors and fixing them automatically
6. Export the generated data to a single CSV

### Step 3 — Explore Your Outputs

```
hr_people_analytics_org_worksite/
├── synth_hr_people_analytics_org_worksite.ipynb   # Full notebook
└── synthetic_hr_people_analytics_org_worksite_data.csv  # Clean CSV
```

Open the notebook to review visualizations, tweak parameters, or regenerate with a different record count.

### Example Prompts

```text
/prompt2data chicago parking meters over the last 6 months
/prompt2data sales data for retail stores across 5 regions
/prompt2data patient visit records for a hospital network
/prompt2data cook times for a brisket
```

---

## What Gets Generated

Each run produces a notebook with the following structure:

| # | Cell | Type |
|---|---|---|
| 1 | Title & description | Markdown |
| 2 | Package installation (`pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`) | Code |
| 3 | Library imports | Code |
| 4 | Data structure explanation | Markdown |
| 5 | Data generation function (parameterized, type-hinted) | Code |
| 6 | Parameter configuration notes | Markdown |
| 7 | Data generation execution | Code |
| 8 | CSV export | Code |
| 9–N | Visualizations (bar, box, scatter, heatmap, etc.) | Code |
| N+1 | Summary statistics | Code |
| N+2 | Validation & quality checks | Code |

---

## Workflow Diagram

See [prompt2data-workflow-digram.md](prompt2data-workflow-digram.md) for the full Mermaid flowchart, or refer to the diagram below:


---

## Microsoft CELA Guidelines for Open Data

When publishing or sharing synthetic datasets, follow the **Microsoft Corporate, External, and Legal Affairs (CELA) Guidelines for Open Data** to ensure compliance with data governance, licensing, and privacy requirements.

Key principles include:

- **Licensing** — Use an approved open data license that clearly states reuse rights.
- **Privacy** — Verify that no real personally identifiable information (PII) leaks into synthetic outputs.
- **Attribution** — Provide clear provenance and generation metadata.
- **Quality** — Document known limitations, biases, and intended use cases.


**Synthetic Data Generation Guidelines**: [https://docs.opensource.microsoft.com/opendata/synthetic-data-guidelines/](https://docs.opensource.microsoft.com/opendata/synthetic-data-guidelines/)

**Seeded Synthetic Data Generation Guidelines**: [https://docs.opensource.microsoft.com/opendata/synthetic-data-guidelines/#seeded-synthetic-data-generation-guidelines](https://docs.opensource.microsoft.com/opendata/synthetic-data-guidelines/#seeded-synthetic-data-generation-guidelines)

📖 **Full guidelines**: [https://docs.opensource.microsoft.com/opendata/](https://docs.opensource.microsoft.com/opendata/)

---

## Presidio: Data Protection and De-identification SDK

[**Microsoft Presidio**](https://microsoft.github.io/presidio/) It helps ensure sensitive data is properly managed and governed. It provides fast identification and anonymization modules for private entities in text and images. 

### How Presidio Complements Prompt2Data

| Use Case | How It Helps |
|---|---|
| **Validate synthetic data** | Run Presidio's analyzer over generated CSVs to confirm zero real PII was accidentally embedded. |
| **Real → Fake pipeline** | Use **Presidio + OpenAI** to turn real text into realistic fake text — a complementary approach to fully synthetic generation. |
| **De-identify before training** | If you augment synthetic data with real-world samples, Presidio can strip PII before the data enters your pipeline. |

### Quick Start

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```
📖 **Full documentation**: [https://microsoft.github.io/presidio/](https://microsoft.github.io/presidio/)

---

## References

- [VS Code Copilot Customization](https://code.visualstudio.com/docs/copilot/copilot-customization)
- [Microsoft Open Data Guidelines](https://docs.opensource.microsoft.com/opendata/)
- [Microsoft Presidio](https://microsoft.github.io/presidio/)

<!-- Contains AI-generated edits. -->