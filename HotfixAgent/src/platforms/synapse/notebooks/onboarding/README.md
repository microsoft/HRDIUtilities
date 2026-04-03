# Synapse Notebooks — Onboarding

> **Status**: Planned

Synapse Analytics pipeline onboarding notebooks will be added here once the
Synapse platform adapter (`src/platforms/synapse/client.py`) is implemented.

The onboarding logic will follow the same pattern as Fabric:
1. Checkpoint table in a Synapse Dedicated/Serverless SQL pool or Delta Lake
2. Helper stored procedure or notebook for CHECK_ALL / UPDATE / RESET
3. Pipeline transformation to wrap activities with checkpoint logic

Key differences from Fabric:
- Uses ARM API instead of Fabric REST API
- Pipeline definitions follow ADF JSON schema
- Checkpoint storage may use SQL pool tables instead of Delta Lake
