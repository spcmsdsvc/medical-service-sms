# Restore drill (quarterly)

Proves the off-site copies in Cloudflare R2 open and are current. It does **not** restore
production; replacing the live database is a separate procedure.

1. Cloudflare dashboard → R2 → bucket `medical-service-backups` → `hourly/` (or `daily/`).
   Download the newest `medical_service_db_….sqlite.gz`.
2. Unzip it with 7-Zip.
3. Open the `.sqlite` file in DB Browser for SQLite.
4. Execute SQL: `PRAGMA integrity_check;` → must return `ok`.
5. Check the newest TSR and the newest user match the live system (allow for changes made
   after the copy's hour).
6. Delete the downloaded files from the computer.
7. Add a line below.

| Date | Copy checked | integrity_check | Newest TSR matched | By |
| --- | --- | --- | --- | --- |
