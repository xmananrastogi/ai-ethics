# Backup Strategy & Disaster Recovery

As a legally compliant healthcare data system, the THOA Screening platform requires rigorous data backup strategies. The infrastructure comprises two primary stateful components that require regular backups: the PostgreSQL database and the document uploads directory.

## 1. Database (PostgreSQL) Backups

The PostgreSQL database contains the case workflows, extracted data, audit logs, and anonymized relationship details. Since it stores the `AuditLog` (which must be immutable and verifiable), loss of this database is catastrophic.

### Recommended Strategy
- **Automated Nightly Backups**: Run `pg_dump` via a cron job on the host machine to generate a SQL dump of the database.
- **WAL Archiving / Point-In-Time Recovery (PITR)**: For production workloads, enable PostgreSQL Write-Ahead Log (WAL) archiving to an external storage service (like AWS S3) using a tool like `pgBackRest` or `wal-g`. This allows recovery to any specific second in time before a failure.
- **Retention Policy**: Retain daily backups for 30 days, weekly backups for 1 year, and yearly backups for 10 years (as mandated by clinical data retention policies).

**Example Nightly Backup Cron (Host Machine):**
```bash
0 2 * * * docker exec thoa-screening-db-1 pg_dump -U thoa_user thoa_db > /path/to/backups/db_backup_$(date +\%Y\%m\%d).sql
```

## 2. Document Uploads Backups

Uploaded legal and medical documents are stored on the file system in the `./uploads` directory (mounted to `/app/uploads` in the containers).

### Recommended Strategy
- **Continuous Sync**: Sync the `uploads` directory to an object storage bucket (e.g., AWS S3, Google Cloud Storage) or a remote Network Attached Storage (NAS) server to ensure documents are not lost if the host machine's drive fails.
- **Tooling**: Use `rsync`, `rclone`, or `aws s3 sync`.

**Example Sync Cron (Host Machine):**
```bash
30 * * * * rsync -avz /path/to/thoa_screening/uploads/ user@backup-server:/var/backups/thoa_uploads/
```
*(Runs every hour at the 30-minute mark)*

## 3. Encryption at Rest

When backing up to external storage or cloud providers, **all backups must be encrypted at rest**. Ensure your S3 buckets have default AES-256 encryption enabled, or use client-side encryption before transferring the files. The database already contains application-layer AES-256-GCM encryption for Aadhaar and PAN numbers, but full database/volume encryption is still required for holistic DPDP Act compliance.
