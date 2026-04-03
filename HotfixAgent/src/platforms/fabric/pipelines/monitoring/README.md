# Fabric Pipelines — Monitoring

Pipeline definitions for checkpoint monitoring and health checks.

## Planned

- **CheckpointHealthCheck** — scheduled pipeline that queries the checkpoint table
  for stale FAILED records and alerts via Teams
- **PipelineLineageScan** — scheduled pipeline that collects lineage data across
  all workspace pipelines
