**The Problem**

Migrating metadata between platforms isn’t straightforward due to:

No out-of-the-box support for transferring metadata between PaaS and SaaS environments.

Manual limitations in editing metadata at scale—especially for large catalogs.

Legacy metadata clutter, which introduces governance noise and reduces discoverability.


**Migration Challenges**

We identified key technical and operational roadblocks:

API differences between PaaS and SaaS requiring transformation logic.

Classification and glossary mismatches, complicating 1:1 mapping.

Ownership & access control inconsistencies between platforms.

Increased metadata complexity needed by SaaS for governance capabilities like classification, sensitivity labelling, and policy enforcement.

**Our Solution: Metadata Migration Accelerator Utility**

We built a robust utility that allows organizations to extract, edit, validate, and push metadata during the migration process—all through a flexible and modular pipeline.

**Key Capabilities:**

Fetch Metadata from Azure Purview (PaaS)

Using REST APIs, the tool extracts complete metadata catalogs and stores them in a structured format.

Editable Excel Layer for Bulk Operations

Metadata is exported to an Excel file for data stewards and engineers to clean, tag, or remove entries—empowering teams with easy bulk-edit capabilities.

Scheduled Processing with Azure Functions

A serverless compute layer enables automated, rule-driven metadata validation and processing at regular intervals.

Push to Microsoft Purview (SaaS)

Once reviewed and finalized, enriched metadata is loaded into the SaaS environment via Microsoft Purview APIs.
