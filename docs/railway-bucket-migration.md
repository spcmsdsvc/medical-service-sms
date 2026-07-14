# Railway Bucket Migration Runbook

## Initial Deployment

1. Create one private Railway Storage Bucket in the same region as the web service.
2. Inject the bucket credentials into the web service using Railway variable references.
3. Set the application variables below and deploy:

```text
FILE_STORAGE_MODE=mirror
STORAGE_BUCKET_NAME=${{Bucket.BUCKET}}
STORAGE_BUCKET_ENDPOINT=${{Bucket.ENDPOINT}}
STORAGE_BUCKET_ACCESS_KEY=${{Bucket.ACCESS_KEY_ID}}
STORAGE_BUCKET_SECRET_KEY=${{Bucket.SECRET_ACCESS_KEY}}
STORAGE_BUCKET_REGION=${{Bucket.REGION}}
STORAGE_BUCKET_URL_STYLE=virtual
STORAGE_VOLUME_FALLBACK=true
```

Replace `Bucket` with the Railway bucket service name used by the variable-reference picker.
The credential aliases injected automatically by Railway are also supported.

## Migration

1. Open `Settings > Storage` as a superadmin.
2. Confirm the bucket connection is healthy and the active mode is `MIRROR`.
3. Select `Migrate Next 25` until no pending files remain.
4. Select `Verify Next 25` until every volume file is SHA-256 verified.
5. Test uploads, previews, downloads, email packages, and deletes for every file family.
6. Set `FILE_STORAGE_MODE=bucket` and redeploy. Keep `STORAGE_VOLUME_FALLBACK=true`.

## Rollback Window

- Keep verified volume upload copies for 30 days after cutover.
- Do not remove `/data/scheduler.db`, TSR email metadata, migration state, or form templates.
- Volume cleanup is a separate, explicitly confirmed operation after the retention window.
- Never commit, upload, replace, or delete `scheduler.db` during file-storage work.
