# R8-07 capture_csv_codec

Status: `SOFTWARE_SOURCE_READY_NOT_RUN`. The CLI streams JSONL-to-CSV and CSV-to-JSONL one row at a time while preserving the exact R7-A 61-field row plus the frozen TX extension by JSON-encoding every CSV cell. Small-fixture string wrappers remain available. It rejects unknown extension versions and legacy 29-column backfill. No observer is created or modified.
