# Alembic Migration Guide

This guide explains how to use Alembic for database migrations in this project, covering common commands and troubleshooting the specific issues encountered during setup.

## Basic Commands

### Generate a New Migration (Revision)
To automatically detect changes in your models and generate a migration script:
```bash
alembic revision --autogenerate -m "Description of change"
```

### Apply Migrations
To update your database to the latest revision:
```bash
alembic upgrade head
```

### Check Migration Status
To see the current revision of your database:
```bash
alembic current
```

---

## Troubleshooting: Problems Faced & Solutions

### 1. Alembic Doesn't Detect New Tables
**Problem:** You run `alembic revision --autogenerate`, but the generated file is empty (contains only `pass` in `upgrade()` and `downgrade()`), even though you've defined your models.

**Root Cause:** Alembic's `env.py` doesn't automatically know about your models. It only "sees" classes that have been imported when it runs.

**Solution:** 
You must explicitly import your model classes in `alembic/env.py` before setting `target_metadata`. 
In this project, we added the following to `alembic/env.py`:
```python
from src.models.db_schemes.cv_analysis_db.base import BaseTable
# CRITICAL: Import all models here so they are registered with BaseTable.metadata
from src.models.db_schemes.cv_analysis_db.db_tables import Project, Asset, DataChunk

target_metadata = BaseTable.metadata
```

### 2. "Target database is not up to date" Error
**Problem:** Running `alembic revision --autogenerate` fails with the error: `FAILED: Target database is not up to date.`

**Root Cause:** Your local database's `alembic_version` table is pointing to an older revision than the latest file in your `alembic/versions/` folder. Alembic requires your database to be at the "head" before it can calculate new changes.

**Solution:**
Synchronize your database with the current migration history before generating a new one:
```bash
alembic upgrade head
```
After this, you can safely run the `--autogenerate` command again.

---

## Best Practices
- **Clean up empty migrations:** If you accidentally generate an empty migration file, delete it from `alembic/versions/` before running a new autogenerate command.
- **Review generated scripts:** Always open the new file in `alembic/versions/` to verify that the `upgrade()` and `downgrade()` functions correctly reflect your changes.
- **Use meaningful messages:** Instead of "test" or "change", use descriptive names like "Add user roles table" or "Rename asset_size column".
