---
description: "Generate comprehensive synthetic relational data for any specified subject with multiple normalized CSV files maintaining referential integrity"
mode: agent
tools: ['codebase', 'githubRepo','editFiles','runNotebooks','runCommands','readNotebookCellOutput']
---

# Synthetic Relational Data Generator

Generate comprehensive synthetic relational data for: **${input:subject}**

You are an expert data scientist, data architect, and synthetic data generator. Create realistic, comprehensive synthetic datasets organized as **multiple normalized CSV files** with proper relational integrity based on the subject provided.

**CRITICAL REQUIREMENT**: Execute every single notebook cell immediately after creating it using `run_notebook_cell`. This ensures code validity, maintains notebook state, and catches errors early in the development process.

**MULTI-TABLE REQUIREMENT**: Always decompose the subject into multiple domain entities and generate a separate CSV file for each entity. Tables must be linked via primary keys and foreign keys to maintain referential integrity across the dataset.

## Output Requirements


## Project Organization

**Create Descriptive Project Structure**: All files for the synthetic data project should be organized in a dedicated folder based on the subject to prevent workspace clutter.

**File Naming Convention**:
1. **Parse Subject**: Extract key concepts from `${input:subject}` for naming
2. **Create Project Folder**: Use format `{parsed_subject}/` (e.g., "weather for 12 states for 12 months" → `weather_12_states_12_months/`)
3. **Notebook File**: `{project_folder}/synth_{parsed_subject}.ipynb`
4. **CSV Files**: One CSV per domain entity — `{project_folder}/synthetic_{parsed_subject}_{entity_name}.csv`

**Examples**:
- "weather for 12 states for 12 months" →
  - Folder: `weather_12_states_12_months/`
  - Notebook: `weather_12_states_12_months/synth_weather_12_states_12_months.ipynb`
  - CSVs:
    - `weather_12_states_12_months/synthetic_weather_12_states_12_months_states.csv`
    - `weather_12_states_12_months/synthetic_weather_12_states_12_months_stations.csv`
    - `weather_12_states_12_months/synthetic_weather_12_states_12_months_observations.csv`
- "sales data for retail stores" →
  - Folder: `sales_data_retail_stores/`
  - Notebook: `sales_data_retail_stores/synth_sales_data_retail_stores.ipynb`
  - CSVs:
    - `sales_data_retail_stores/synthetic_sales_data_retail_stores_stores.csv`
    - `sales_data_retail_stores/synthetic_sales_data_retail_stores_products.csv`
    - `sales_data_retail_stores/synthetic_sales_data_retail_stores_customers.csv`
    - `sales_data_retail_stores/synthetic_sales_data_retail_stores_transactions.csv`

**IMPORTANT**: Export all CSV files in a single designated export cell. Each entity gets its own CSV file. Never duplicate exports.

### Notebook Structure Requirements
Create a well-structured notebook with the following cells:

1. **Title Cell** (Markdown): Clear title with the subject
2. **Package Installation Cell** (Code): Install required packages using `%pip install pandas numpy matplotlib seaborn scipy`
3. **Library Import Cell** (Code): Import all required libraries
4. **Domain Entity Analysis** (Markdown): Identify all entities in the domain, their attributes, and relationships (see Domain Entity Identification below)
5. **Relational Schema Definition** (Code): Define the schema as a data dictionary — tables, columns, data types, primary keys, and foreign keys
6. **Data Generation Functions** (Code): One function per entity/table, generating data with realistic patterns. Parent/lookup tables must be generated before child/fact tables so foreign keys reference valid primary keys.
7. **Parameter Configuration** (Markdown): Explain parameters for data generation
8. **Data Generation Execution** (Code): Execute all generation functions in dependency order (parent tables first)
9. **Referential Integrity Validation** (Code): Verify all foreign keys resolve, no orphan records exist, and cardinality constraints are met
10. **Data Export** (Code): Export each DataFrame to its own CSV file in the project folder
11. **Entity-Relationship Diagram** (Markdown): A text-based ER diagram showing tables and their relationships
12. **Multiple Visualization Cells** (Code): Charts using matplotlib and seaborn showing patterns within and across tables
13. **Summary Statistics** (Code): Comprehensive data analysis per table
14. **Validation & Quality Checks** (Code): Verify data realism and cross-table consistency

## Analysis & Planning

First, analyze the subject domain:
- Research what realistic data should look like for this subject
- Identify key variables and data fields that are essential
- Define relationships between variables (correlations, dependencies)
- Consider temporal patterns (seasonality, trends, cyclical behavior)
- Understand geographic or demographic variations if applicable

### Domain Entity Identification

Decompose `${input:subject}` into a **normalized relational model**. This is a mandatory first step before any code generation.

1. **Identify Entities**: List all distinct real-world objects or concepts in the domain (e.g., for "hospital patient records" → Patients, Doctors, Departments, Visits, Diagnoses, Medications)
2. **Classify Each Entity**:
   - **Lookup/Dimension tables**: Relatively static reference data (e.g., Departments, Product Categories, States)
   - **Fact/Transaction tables**: Event-driven records that reference lookup tables (e.g., Sales, Visits, Orders)
3. **Define Relationships**: For every pair of related entities, specify:
   - Relationship type: one-to-one, one-to-many, or many-to-many
   - The foreign key column and which table it references
   - Cardinality constraints (e.g., each Order must have at least 1 OrderItem)
4. **Determine Generation Order**: Build a dependency graph so parent/lookup tables are generated before child/fact tables
5. **Aim for 3–7 tables** depending on domain complexity. Every subject should produce at least 3 CSV files.

**Entity Identification Examples**:

| Subject | Entities (Tables) | Key Relationships |
|---|---|---|
| Hospital patient records | Patients, Doctors, Departments, Visits, Diagnoses | Visits → Patients (FK), Visits → Doctors (FK), Doctors → Departments (FK) |
| E-commerce sales | Customers, Products, Categories, Orders, OrderItems | Orders → Customers (FK), OrderItems → Orders (FK), Products → Categories (FK) |
| School management | Students, Teachers, Courses, Enrollments, Grades | Enrollments → Students (FK), Enrollments → Courses (FK), Courses → Teachers (FK) |
| Weather monitoring | States, Stations, Observations, Alerts | Stations → States (FK), Observations → Stations (FK), Alerts → Stations (FK) |

## Data Structure Requirements

Design a thoughtful data structure that includes:

### Relational Schema Design

Before generating data, define a complete relational schema:

- **Primary Keys**: Every table must have a unique primary key column (e.g., `patient_id`, `order_id`). Use sequential integers or meaningful codes.
- **Foreign Keys**: Child tables must include foreign key columns that reference the primary key of a parent table. Foreign key values must only contain values that exist in the referenced parent table.
- **Referential Integrity**: No orphan records allowed — every foreign key value must resolve to an existing parent record.
- **Cardinality**: Define expected row counts per table. Fact tables typically have more rows than lookup tables (e.g., 50 departments, 500 employees, 10000 transactions).
- **Normalization**: Avoid repeating data across tables. Store each fact once and reference it via keys.
- **Junction Tables**: For many-to-many relationships, create a junction/bridge table with foreign keys to both related tables.

Example schema definition in code:
```python
SCHEMA = {
    'departments': {
        'primary_key': 'department_id',
        'foreign_keys': {},
        'row_count': 20
    },
    'employees': {
        'primary_key': 'employee_id',
        'foreign_keys': {'department_id': 'departments.department_id'},
        'row_count': 500
    },
    'projects': {
        'primary_key': 'project_id',
        'foreign_keys': {'department_id': 'departments.department_id'},
        'row_count': 100
    },
    'assignments': {
        'primary_key': 'assignment_id',
        'foreign_keys': {
            'employee_id': 'employees.employee_id',
            'project_id': 'projects.project_id'
        },
        'row_count': 2000
    }
}
```

### Date and Time Handling Requirements
When generating or manipulating dates and times, ensure:
- Convert any value sampled from `pd.date_range` to Python `datetime.date` or `datetime.datetime` using `pd.Timestamp(day).date()` or `pd.Timestamp(day).to_pydatetime()`
- Cast any integer value used in `timedelta` to Python `int` using `int(value)` before passing to `timedelta`
- Never pass numpy types directly to Python standard library date/time functions

Example:
```python
day = np.random.choice(pd.date_range(start=start_date, end=end_date))
day = pd.Timestamp(day).date()  # Ensures Python datetime.date
hour = int(np.random.choice(range(8, 19)))
minute = int(np.random.randint(0, 60))
start_time = datetime.combine(day, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
```


### Data Types & Ranges
- Use appropriate data types (numeric, categorical, datetime, text, boolean)
- Ensure all values fall within believable, realistic bounds
- Include natural outliers and edge cases that would occur in real data
- Consider data quality issues (some missing values, slight inconsistencies)

### Realistic Distributions
- Use appropriate statistical distributions for different variable types
- Model correlations and dependencies between related variables
- Include natural noise and variation patterns
- Account for business rules or physical constraints

### Domain-Specific Patterns

#### For Business Data:
- Seasonal trends in sales, revenue, customer behavior
- Geographic and demographic variations
- Market dynamics and competitive effects
- Supply/demand patterns and inventory cycles
- Customer lifecycle and behavior patterns

#### For Scientific/Technical Data:
- Measurement uncertainties and instrument precision
- Physical laws and natural constraints
- Environmental factors and their effects
- Sampling frequencies and data collection patterns
- Natural variations and experimental noise

#### For Social/Behavioral Data:
- Demographic distributions matching real populations
- Cultural and regional variations
- Social network effects and clustering
- Temporal patterns (time-of-day, day-of-week, seasonal)
- Behavioral preferences and decision patterns

## Implementation Guide

**Environment Setup**
1. Use `configure_python_environment` to automatically set up the Python environment
2. Use `configure_notebook` to prepare the notebook environment
3. Use `notebook_install_packages` to install: `['pandas', 'numpy', 'matplotlib', 'seaborn', 'scipy']`

**Project Creation**
1. Parse `${input:subject}` to extract key concepts for naming
2. Create descriptive project folder using `create_directory`
3. Create notebook using `create_new_jupyter_notebook` with query: "Generate synthetic data for ${input:subject} with realistic patterns and comprehensive analysis"

**Notebook Development**
1. Use `edit_notebook_file` to create structured cells as outlined above
2. **MANDATORY**: Use `run_notebook_cell` immediately after creating each cell
3. Ensure all code executes without errors before proceeding
4. Generate parent/lookup tables before child/fact tables to ensure valid foreign keys
5. Export all CSV files in a single designated export cell
6. Validate referential integrity across all tables before export

**Validation**
- Run all cells to ensure end-to-end functionality
- Confirm realistic data patterns and distributions
- Verify all foreign key relationships are valid (no orphan records)
- Confirm project folder contains the notebook and all CSV files

## Code Template Structure

```python
# Cell 1: Package Installation
%pip install pandas numpy matplotlib seaborn scipy

# Cell 2: Library Imports
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import random
from scipy import stats
import os

# Cell 3: Relational Schema Definition
SCHEMA = {
    'table_name_1': {
        'primary_key': 'id_column',
        'foreign_keys': {},
        'row_count': 50,
        'description': 'Lookup/dimension table'
    },
    'table_name_2': {
        'primary_key': 'id_column',
        'foreign_keys': {'fk_column': 'table_name_1.id_column'},
        'row_count': 500,
        'description': 'Fact/transaction table'
    },
    # ... additional tables
}

# Cell 4: Data Generation Functions (one per entity)
def generate_table_name_1(num_records: int = 50) -> pd.DataFrame:
    """
    Generate lookup/dimension table for ${input:subject}.
    This is a parent table — no foreign key dependencies.
    """
    ids = range(1, num_records + 1)
    # Generate realistic attributes
    return pd.DataFrame({'id_column': ids, ...})

def generate_table_name_2(
    num_records: int = 500,
    parent_df: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Generate fact/transaction table for ${input:subject}.
    Foreign keys reference parent table to ensure referential integrity.
    """
    valid_parent_ids = parent_df['id_column'].tolist()
    fk_values = np.random.choice(valid_parent_ids, size=num_records)
    # Generate realistic attributes correlated with parent data
    return pd.DataFrame({'id_column': range(1, num_records + 1),
                         'fk_column': fk_values, ...})

# Cell 5: Execute Data Generation (dependency order)
df_table_1 = generate_table_name_1(num_records=SCHEMA['table_name_1']['row_count'])
df_table_2 = generate_table_name_2(
    num_records=SCHEMA['table_name_2']['row_count'],
    parent_df=df_table_1
)
# ... generate remaining tables in dependency order

all_tables = {
    'table_name_1': df_table_1,
    'table_name_2': df_table_2,
    # ... all generated DataFrames
}

# Cell 6: Referential Integrity Validation
def validate_referential_integrity(tables: dict, schema: dict) -> None:
    """Verify all foreign keys resolve to valid parent records."""
    for table_name, table_schema in schema.items():
        df = tables[table_name]
        for fk_col, ref in table_schema['foreign_keys'].items():
            ref_table, ref_col = ref.split('.')
            parent_ids = set(tables[ref_table][ref_col])
            child_ids = set(df[fk_col])
            orphans = child_ids - parent_ids
            if orphans:
                raise ValueError(
                    f"Orphan records in {table_name}.{fk_col}: {orphans}"
                )
            print(f"  {table_name}.{fk_col} -> {ref}: ALL VALID")
    print("Referential integrity check PASSED for all tables.")

validate_referential_integrity(all_tables, SCHEMA)

# Cell 7: Export All Tables to CSV
subject = "${input:subject}"
SUBJECT_CLEAN = (subject.lower()
                       .replace(" for ", "_")
                       .replace(" across ", "_")
                       .replace(" in ", "_")
                       .replace(" ", "_")
                       .replace("-", "_")
                       .replace("__", "_"))

for table_name, df in all_tables.items():
    filename = f'synthetic_{SUBJECT_CLEAN}_{table_name}.csv'
    df.to_csv(filename, index=False)
    print(f"Saved {table_name}: {filename} ({len(df)} rows, {len(df.columns)} columns)")

print(f"\nTotal files exported: {len(all_tables)}")

# Cell 8-11: Multiple Visualization Cells
# Create charts using matplotlib and seaborn
# Include cross-table relationship visualizations
# Include map visualizations if data contains geographic information

# Cell 12: Summary and Validation
for table_name, df in all_tables.items():
    print(f"\n=== {table_name.upper()} SUMMARY ===")
    print(f"Shape: {df.shape}")
    print(df.describe())
print(f"\nGeneration timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
```

## Required Outputs

1. **Jupyter Notebook**: Well-structured notebook with organized cells
2. **Data Generation Functions**: One modular, parameterized function per entity/table with type hints
3. **Realistic Data**: Values that domain experts would find believable across all tables
4. **Multiple CSV Exports**: One CSV file per domain entity, all in the project folder
5. **Relational Integrity**: All foreign keys valid, no orphan records, proper cardinality
6. **Multiple Visualizations**: Charts using matplotlib and seaborn, including cross-table relationship charts. Include map visualizations if data contains geographic information.
7. **Statistical Summary**: Comprehensive descriptive statistics per table
8. **Data Validation**: Quality checks ensuring realism and referential integrity
9. **Documentation**: Clear markdown explanations including ER diagram and relationship descriptions

## Quality Standards

- **Realism**: Data should look authentic to subject matter experts
- **Completeness**: Cover all important aspects of the domain across multiple tables
- **Referential Integrity**: All foreign key relationships are valid and verifiable
- **Normalization**: No redundant data — each fact stored once and referenced via keys
- **Scalability**: Functions should work with different dataset sizes
- **Flexibility**: Allow customization through parameters
- **Statistical Validity**: Distributions and correlations make sense within and across tables
- **Usability**: Data ready for joins, analysis, modeling, or visualization

## Final Deliverables

1. **Project Folder**: Organized folder structure with descriptive name
2. **Jupyter Notebook**: Complete implementation with all required cells
3. **Multiple CSV Data Files**: One CSV per domain entity, all with consistent naming
4. **Rich Documentation**: Clear explanations including ER diagram and relationship descriptions
5. **Multiple Visualizations**: Charts showing data patterns within and across tables
6. **Referential Integrity Proof**: Validation output confirming all foreign keys are valid
7. **Data Validation**: Evidence that synthetic data is realistic and high-quality

**Project Structure Example**:
```
sales_data_retail_stores/
├── synth_sales_data_retail_stores.ipynb
├── synthetic_sales_data_retail_stores_stores.csv
├── synthetic_sales_data_retail_stores_products.csv
├── synthetic_sales_data_retail_stores_categories.csv
├── synthetic_sales_data_retail_stores_customers.csv
└── synthetic_sales_data_retail_stores_transactions.csv
```

<!-- Contains AI-generated edits. -->
