# Include/exclude

S3 client shows multiple files:

```sh
$ mc ls s3/default-bucket/volumes/
[2026-07-26 19:14:13 CST] 5.1KiB STANDARD shared-file.md
[2026-07-26 20:50:36 CST]  30KiB STANDARD storagegrid.log
```

OpenSharing tells us there's only one:

```sh
$ curl -s \
  http://127.0.0.1:8000/shares/files-share/schemas/log-schema/volumes/docs-dir/files \
  | jq
{
  "items": [
    {
      "file_path": "storagegrid.log",
      "size": 30596
    }
  ]
}
```

Why? Because that is how OpenSharing Volumes share configuration is done:

```yaml
      - name: files-share
        recipients:
          oidcEmails:
            - bob@example.com
          oidcSubjects: []
        schemas:
          - name: log-schema
            volumes:
              - name: docs-dir
                storageLocation: s3://default-bucket/volumes/
                include: ["*.log"]
                exclude: [".internal/*"]
```
