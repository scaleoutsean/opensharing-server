# OpenSharing Server for NetApp StorageGRID and Versity S3 Gateway

An opinionated OpenSharing server for NetApp StorageGRID and Versity S3 Gateway (primary focus is sharing NetApp E-Series data) object stores. 

[This page](https://scaleoutsean.github.io/2026/07/22/opensharing-volumes-tables-versity-vgw-netapp-storagegrid.html) has some background on the motivation and use cases.

The OpenSharing Server is Go-based and distributed as a free binary release (Linux on AMD64 and ARM64, Windows) with a Docker Compose stack for evaluation, testing and development (although nothing prevents its use in production, you probably shouldn't).

- Tested object stores: 
  - Versity S3 Gateway 1.7.0 (with S3/RDMA as of [8bd73a4](https://github.com/versity/versitygw/commit/8bd73a45eea3bce090e89e8fc97ad2ccfdf1b935) from early August 2026) and 1.6.0
  - StorageGRID 12.1, 12.0 

## Features

- Bearer token authorization
- Supports **named** Tables and Volumes (files)
- Supports S3/RDMA (only with Versity S3 Gateway with S3/RDMA)
- List objects with include/exclude pattern for objects in OpenSharing Volumes
- List sharing candidates limited to Volume candidates, i.e. buckets
- Live reload of sharing configuration

OpenSharing server currently does not apply Delta transaction semantics to OpenSharing Tables - they're assumed to be static. 
It is something that could be done by a separate application (especially with Versity S3 Gateway, where [such applications](https://scaleoutsean.github.io/2026/06/16/netapp-eseries-iot-compaction-opensharing.html) can run on the same Linux host) or OpenSharing Server itself.

Data paths:

- OpenSharing API metadata and policy checks are handled by OpenSharing Go service
- S3 bucket/object discovery and table/volume listings are live S3-compatible API calls
- S3 object reads are direct, using presigned URLs built from the configured external S3 API endpoint
  - When S3/RDMA-enabled Versity S3 Gateway is serving data over an RoCEv2-enabled network, S3/RDMA-capable clients can GET objects over RDMA

Other OpenSharing objects aren't implemented yet because I haven't needed them. The Versity S3 Gateway does not support [AWS STS (Assume Role)](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html), so I'm not in a hurry to implement it just for StorageGRID because I haven't heard of anyone who needs OpenSharing with STS support (likely complicated, as OpenSharing and S3 each need OAuth2).

## Use cases 

- NetApp E-Series with Versity S3 Gateway: securely share data stored on E-Series volumes without copying it to NAS or external S3 or managing complex services
- NetApp StorageGRID: OpenSharing access to Tables, Volumes (buckets) for zero-copy analytics, machine learning, and general file sharing

Currently neither StorageGRID nor E-Series have an official solution for OpenSharing. This server is the first to offer a working implementation and it enables early testing and development using standard, open APIs.

## Get started 

Running from CLI is recommended for quick evaluation, especially with existing S3 storage. It requires access to existing Versity S3 Gateway or StorageGRID S3 API endpoint and valid S3 credentials.

Docker Compose is recommended for evaluation with built-in or own OAuth2. 

**NOTE:** to make it easy to get started, various service files have prepopulated credentials:

- **`./dex-config/config.yaml`**: Oauth2 credentials and settings such as token TTL
- **`./config/shares.yaml`**: user IDs and bucket configuration
- **`./docker-compose.yaml`**: Versity S3 Gateway admin credentials (`s3`), and various other in `opensharing-app`, `api`

If you are concerned about that, either:

- change the credentials, *or* 
- set up own S3 server instance and run just OpenSharing Server from the CLI using a localhost `HTTP_ADDR` and `AUTH_REQUIRED=false` (see *CLI with own S3 service* further below)

### StorageGRID and Versity S3 Gateway 

- Docker Compose comes with a Versity S3 Gateway container (HTTP/27070)
- If you want to use your own S3 service, configure OpenSharing service to use it by editing `docker-compose.yaml` 
  - StorageGRID S3 API for tenants usually defaults to HTTPS served on port 10443
  - Versity S3 Gateway defaults to HTTP on port 7070 (in `docker-compose.yaml` it uses different ports to avoid potential conflict with local instances)
  - Connecting to HTTPS S3 API targets requires a valid TLS certificate or saved PEM chain (you may put it in `./certs/` and set in OpenSharing Server environment variables). You may also disable TLS certificate verification

Built-in Versity S3 Gateway has a Web UI at `http://127.0.0.1:27080/`. If you want to upload objects from the Web UI, use that. Feel free to customize or hide behind a reverse HTTPS proxy.

There's a number of places where one can screw up, so at least initially, it's recommended to use it as-is or disable it if you don't want to make it accessible. These are the details you need to get right when accessing the Web UI.

![VGW Web UI](/images/s3_vgw_web_ui_settings.png)

If you want to make the Web UI or S3 API inaccessible to others, change `docker-compose.yaml` to limit access to `localhost` clients.

### CLI with own S3 service

This approach is simple: authentication is disabled, so you can immediately focus on using OpenSharing server. 

Edit `./config/shares.yaml` (including `storageLocation` which has the S3 bucket detail) if you want to use own data, or create the same bucket and upload the sample data from `./sample-data/` to avoid editing `shares.yaml`.

```sh
$ export AUTH_REQUIRED=false \
  HTTP_ADDR=127.0.0.1:8000 \
  S3_INTERNAL_ENDPOINT=https://192.168.1.211:10443 \
  S3_EXTERNAL_ENDPOINT=https://192.168.1.211:10443 \
  S3_ACCESS_KEY=bla \
  S3_SECRET_KEY=bla-bla \
  REGISTRY_PATH=config/shares.yaml \
  S3_CA_BUNDLE=$PWD/certs/storagegrid-ca.crt \
  S3_TLS_VERIFY=true
$ ./opensharing-server
```

`HTTP_ADDR` controls bind address and port. The default is `:8000` (all interfaces). For local-only CLI testing, prefer `127.0.0.1:8000`. 

**NOTE:** For "experimental" S3/RDMA with VGW RDMA, see the section at the bottom. There's no standard S3/RDMA client, so this isn't included in "standard" evaluation.

Windows version (PowerShell 7 terminal):

```ps1
$Env:AUTH_REQUIRED="false"
$Env:HTTP_ADDR="127.0.0.1:8000"
$Env:S3_INTERNAL_ENDPOINT="https://192.168.1.211:10443"
$Env:S3_EXTERNAL_ENDPOINT="https://192.168.1.211:10443"
$Env:S3_ACCESS_KEY="bla"
$Env:S3_SECRET_KEY="bla-bla"
$Env:REGISTRY_PATH=".\config\shares.yaml"
./opensharing-server
```

Note that there's no built-in online help because OpenSharing server is made to run containerized.

If the server starts as expected, skip to Evaluation section. 

### Docker Compose stack 

Authentication/authorization may be disabled in docker-compose.yaml (`AUTH_REQUIRED=false`):
- If you disable it, you don't need OAuth2 service and you can use OpenSharing without JWT 
- If you do not disable it, you need OAuth2 service (either built-in or own)

If authentication is enabled, some experience with OAuth2 is desirable. There are two ways to do this:
- Point OpenSharing server to own OAuth2 endpoint by editing OpenSharing API server's configuration in `docker-compose.yaml`
- Deploy Docker Compose to a VM with the `dex` hostname. This is **required** so that OAuth2 can find itself on localhost, since `dex` is hard-coded in container names and links (e.g., `./dex-config/config.yaml`).

File and directory edits and changes: 
- `./docker-compose.yaml` 
- Create directories for Versity S3 Gateway if you don't have own S3 service: `mkdir data; chmod -R 777 data` 
- `./config/shares.yaml` defines Tables and Volumes shares. If you don't use data from `./sample-data/`, modify this file to suit your bucket name and table/file name(s) 

Confirm containers that you expect to be running are all running. After that, skip to Evaluation section. 

**NOTE:** Compose stack isn't enabled for S3/RDMA because VGW with S3/RDMA hasn't been released yet and it is expected to change rapidly. If you evaluate VGW with S3/RDMA, run OpenSharing from the CLI (see instructions at the bottom of this page).

### (Optional) reverse HTTPS proxy (API gateway) 

All services can be delivered over HTTPS and TLS can terminate on a reverse HTTPS proxy.

This isn't included because there's too much variety in everyone's preferred stack and configuration.

## Evaluation 

Users running in CLI mode don't need to provide JWT token in requests because authentication is disabled.

The steps below assume no authentication (and omit authentication headers in `curl` requests).

### Upload or create sample data and configure shares for OpenSharing server 

`./sample-data` has several small files that can be used in evaluation. We'll use MinIO client (mc) which you can download [here](https://github.com/scaleoutsean/minio-client) or MinIO, but you may also upload the sample files using the Web UI in Versity S3 Gateway or NetApp StorageGRID Tenant UI.

Configure your S3 CLI by following your client's configuration instructions.

```sh 
mc alias set -h # hint: mc alias set s3 ${S3_EXTERNAL_ENDPOINT} ${S3_ACCESS_KEY} ${S3_SECRET_KEY}
mc mb s3://sample-bucket # using alias 's3' to create bucket 'sample-bucket'
mc cp -r sample-data/tables s3://sample-bucket/ # copy sample tables data to sample-bucket
mc cp -r sample-data/volumes s3://sample-bucket/ # copy sample volumes data to sample-bucket
```

My bucket with files uploaded:

```sh
$ mc ls -r s3/default-bucket/
[2026-07-26 19:14:18 CST] 2.9KiB STANDARD tables/iot_silver_table/iot_silver_table.parquet
[2026-07-26 19:14:18 CST] 3.1KiB STANDARD tables/test-object.parquet
[2026-07-26 21:00:34 CST]   909B STANDARD volumes/shared-file.md
[2026-07-26 20:50:36 CST]  30KiB STANDARD volumes/storagegrid.log
```

### Basic checks 

Check the OpenSharing server is running.

```sh
curl -s http://127.0.0.1:8000/healthz | jq
```

### Versity S3 Gateway (if used) 

If running built-in Versity S3 Gateway, you can access it at http://127.0.0.1:27080/, login with admin credentials from `docker-compose.yaml` and create buckets and upload data to be shared.

As you have noticed, Versity buckets are subdirectories below root directory, in this case `./data/` (which has to be created manually). In real life, if your server mounts an E-Series LUN at `/data`, you wouldn't start Versity S3 Gateway from `/` to share `/data` as a bucket, but would instead change the filesystem mount point to something like `/buckets/data`, remount and then run Versity S3 from `./buckets` as its root path.

You can also enable read-only mode for Versity S3 Gateway, which is useful for OpenSharing when data is not updated, or when it's not updated directly via S3 (meaning, you use Linux shell commands to create or copy data/files in your buckets). See the Versity S3 Gateway documentation for the details. OpenSharing server enables read-only access via pre-signed URLs, but using read-only mode on Versity S3 Gateway makes it secure from overwrites via Versity's S3 API endpoint.

### JWT (if used)

If built-in authentication is enabled and OpenSharing server configured to use it:

- go to http://dex:5555/ and click on `Login` (leave all fields empty)
- that will bounce you to http://dex:5556/dex/auth/local/login where you can login with Alice's credentials from `./dex/config.yaml` (email: alice@example.com, password: 123123123)
- next, click on `Grant Access` and `Access Token` is the JWT aka Bearer Token you need to use to authenticate against OpenSharing service

Note that `./config/shares.yaml` may or may not authorize Alice to see certain OpenSharing share types.

If your VM isn't named `dex` as suggested earlier, this probably won't work. You may restart OpenSharing server with authentication disabled in order to continue.

We continue assuming authentication is disabled, so we won't pass the token in `curl` commands.

### Get shares and schemas

Get all shares:

```sh
curl -s http://127.0.0.1:8000/shares | jq
```

Using the sample configuration YAML, we expect to see three.

```json
{
  "items": [
    {
      "name": "report-share"
    },
    {
      "name": "analytics-share"
    },
    {
      "name": "files-share"
    }
  ]
}
```

Find share candidates:

```sh
curl -s http://127.0.0.1:8000/discovery/candidates | jq
```

This isn't OpenSharing, but a simple convenience method that lists buckets that *could* be shared. 

This doesn't update shares, either. That has to be done manually and authorized recipients (if auth is not disabled) have to be set as well.

### OpenSharing Volumes

To see schemas in the OpenSharing Volumes share called `files-share`:

```sh
curl -s   http://127.0.0.1:8000/shares/files-share/schemas/ | jq
```

I have just one.

```json
{
  "items": [
    {
      "name": "log-schema",
      "share": "files-share"
    }
  ]
}
```

```sh
curl -s   http://127.0.0.1:8000/shares/files-share/schemas/log-schema/volumes | jq
```

In this case, my "volumes" is really just a path within a bucket, although it could be an entire bucket.

```json
{
  "items": [
    {
      "name": "docs-dir",
      "schema": "log-schema",
      "share": "files-share",
      "shareId": "share:default:files-share",
      "id": "volume:default:files-share:log-schema:docs-dir",
      "storageLocation": "s3://default-bucket/volumes/"
    }
  ]
}
```

Since there's no individual file/object, I need to get information on the "directory" (path):

```sh
$ curl -s \
  http://127.0.0.1:8000/shares/files-share/schemas/log-schema/volumes/docs-dir/files \
  jq
```

If you look at `shares.yaml`, and compare with the output of `mc ls` for the path within your bucket, you'll see server-side filtering is in place:

```json
{
  "items": [
    {
      "file_path": "storagegrid.log",
      "size": 30596
    }
  ]
}
```

Note that, if a volume `storageLocation` points to a single object instead of a bucket or prefix, the file list exposes that object by basename. This shows the location of shared files for "single object" shares on S3:

```json
{
  "items": [
    {
      "name": "docs-dir",
      "schema": "log-schema",
      "share": "files-share",
      "shareId": "share:default:files-share",
      "id": "volume:default:files-share:log-schema:files-bucket",
      "storageLocation": "s3://default-bucket/volumes/shared-file.md"
    }
  ]
}
```

How to actually get the content of that object? 

To download, we specify the "volume" name and basename.

```sh
curl -s -X POST http://127.0.0.1:8000/shares/files-share/schemas/log-schema/volumes/docs-dir/files/download -H 'Content-Type: application/json' -d '{"file_path":"shared-file.md"}' | jq 
```

This gives you a pre-signed download URL. Although, in this case, our OpenSharing server will do the right thing:

```json
{
  "errorCode": "FORBIDDEN",
  "message": "file_path is not allowed by volume policy"
}
```

Oops! Sorry! Try downloading the allowed file, `storagegrid.log`, instead. 

You can edit the shares configuration file (add or remove and entry) and repeat the curl command to see an updated listing.

In the case `s3://default-bucket/volumes/` did have multiple objects, even in sub-paths, it would have returned a list like this:

```json
{
  "items": [
    {
      "file_path": "a/report.csv",
      "size": 1234
    },
    {
      "file_path": "b/image.png",
      "size": 4567
    }
  ]
}
```

In this case we'd pick individual files, possibly all, and fetch them individually by specifying `file_path` relative to sub-path in the bucket:

```sh
curl -s -X POST \
  http://127.0.0.1:8000/shares/files-share/schemas/log-schema/volumes/docs-dir/files/download \
  -H 'Content-Type: application/json' \
  -d '{"file_path":"a/report.csv"}' \
  | jq
```

### OpenSharing Tables

Find available shares, look for schemas that could have tables, and find their tables:

```sh
curl -s http://127.0.0.1:8000/shares/ | jq
curl -s http://127.0.0.1:8000/shares/report-share/schemas | jq
curl -s http://127.0.0.1:8000/shares/report-share/schemas/report-schema/tables | jq
```

Similar to the situation in Volumes, there's a prefix rather than table "file" name.

```json
{
  "items": [
    {
      "name": "report_table",
      "schema": "report-schema",
      "share": "report-share",
      "shareId": "share:default:report-share",
      "location": "s3://default-bucket/tables/",
      "accessModes": [
        "url"
      ],
      "id": "table:default:report-share:report-schema:report_table"
    }
  ]
}
```

This is a `POST` request:

```sh
curl -sS \
  http://127.0.0.1:8000/shares/report-share/schemas/report-schema/tables \
  | jq
```

This is where Tables are different from Volumes:

```sh
curl -s -X POST http://127.0.0.1:8000/shares/report-share/schemas/report-schema/tables/report_table/query | jq -s
```

We get an NDJSON response - a list of three different things: protocol, metaData, and file.

```json
[
  {
    "protocol": {
      "minReaderVersion": 1
    }
  },
  {
    "metaData": {
      "format": {
        "provider": "parquet"
      },
      "id": "table:default:report-share:report-schema:report_table",
      "name": "report_table",
      "partitionColumns": [],
      "schema": "report-schema",
      "schemaString": "{\"type\":\"struct\",\"fields\":[{\"name\":\"A\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}},{\"name\":\"B\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}},{\"name\":\"C\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}},{\"name\":\"D\",\"type\":\"long\",\"nullable\":true,\"metadata\":{}}]}",
      "share": "report-share"
    }
  },
  {
    "file": {
      "id": "tables/test-object.parquet",
      "partitionValues": {},
      "size": 3220,
      "url": "https://192.162.1.211:10443/....Amz-Signature=299..."
    }
  }
]
```

You can use either of these approaches:

- Option 1: table metadata endpoint: `GET /shares/report-share/schemas/report-schema/tables/report_table/metadata`
- Option 2: table query endpoint: `POST /shares/report-share/schemas/report-schema/tables/report_table/query`

In both cases, we want the metaData object's `schemaString` field. That is the schema for the table file `#report-share.report-schema.report_table` (`s3/default-bucket/tables/test-object.parquet`) in this case.

```sh
curl -s -X POST http://127.0.0.1:8000/shares/report-share/schemas/report-schema/tables/report_table/query | jq -r 'select(.metaData).metaData.schemaString'
```

As mentioned at the top, this OpenSharing Server doesn't apply Delta transaction semantics to OpenSharing Tables. Tables are assumed to be static. The idea is to read or query Tables for reporting or ingress.

### Configuration files and non-interactive use

- `profile.share` (example below) is a JSON configuration file that contains share configuration including a bearer token. If authentiation is enabled, token expiry (TTL) in `./dex-config/config.yaml` (or your own OAuth) applies
- For non-interactive use with authentication enabled, load your bearer token from environment variable or the share file.

```json
{
  "shareCredentialsVersion": 1,
  "endpoint": "http://127.0.0.1:8000",
  "bearerToken": "eyJh...TsHA"
}
```
- The Python script (`test-client.py`) reads this file, but if authentication is disabled, you can populate `bearerToken` with random characters. To run this script, install `requirements.txt` and execute. It works with data from `./sample-data/`, so it will generate errors if your data are different. Modify it for your own purposes. Assuming an active venv used to install requirements.txt, a `profile.share` with connection specification and a certificate (if TLS is used):

```sh
./.venv/bin/python3 ./test-client.py --profile profile.share --ca-bundle ./certs/storagegrid-ca.crt [--insecure-tls]
```

### S3/RDMA with Versity Gateway 

OpenSharing server works with Versity S3 Gateway with S3/RDMA as of [this commit](https://github.com/versity/versitygw/commit/8bd73a45eea3bce090e89e8fc97ad2ccfdf1b935):

- Make sure VGW with S3/RDMA is fully functional by running tests appropriate for your environment (see [this](https://github.com/versity/versitygw/wiki/RDMA-User)) using their S3/RDMA test client
- Start OpenSharing server from teh CLI with the correct Versity S3 Gateway's RDMA IP address and port (example: `S3_EXTERNAL_RDMA_ENDPOINT=http://192.168.1.13:19100`)

Popular S3 client libraries do not support S3/RDMA, so this can't be tested with `curl` - you need a client that can use S3/RDMA.

GET uses information from standard S3 `HeadObject` to allocate a correctly sized registered buffer. This requires `X-Amz-Rdma-Reply` and verification of `X-Amz-Rdma-Bytes-Transferred`.

Volume request:

```http
POST /shares/{share}/schemas/{schema}/volumes/{volume}/files/rdma-download
Authorization: Bearer <OpenSharing token>
Content-Type: application/json

{"file_path":"example.log","rdma_token":"<opaque token>"}
```

Table request:

```http
POST /shares/{share}/schemas/{schema}/tables/{table}/files/rdma-download
Authorization: Bearer <OpenSharing token>
Content-Type: application/json

{"file_id":"tables/test-object.parquet","rdma_token":"<opaque token>"}
```

Successful response:

```json
{
  "download_url": "https://vgwrdma.example/bucket/key?X-Amz-Algorithm=...",
  "required_headers": {
    "Host": "vgwrdma.example",
    "X-Amz-Rdma-Token": "<opaque token>"
  },
  "size": 35274209
}
```

The client should send `X-Amz-Rdma-Token` with the GET; the HTTP library derives `Host` from `download_url`.

Your workflow would look similar to this (I use sample data for tables from this repo):
- Using standard S3, get OpenSharing tables
- Your client needs to be able to GET objects over RDMA. My Versity `vgwrdma` test used the `rdma` bucket and PUT `cuobjtest-object` there, so I first try that from my S3/RDMA client. You can try any objects from VGW.
- If that works, you can use the steps above to get Tables and Volumes as explained above

```sh
$ curl -s http://127.0.0.1:8000/shares/report-share/schemas/report-schema/tables | jq
{
  "items": [
    {
      "name": "report_table",
      "schema": "report-schema",
      "share": "report-share",
      "shareId": "share:default:report-share",
      "location": "s3://default-bucket/tables/",
      "accessModes": [
        "url"
      ],
      "id": "table:default:report-share:report-schema:report_table"
    }
  ]
}

$ python3 test-rdma-client.py direct-get --s3-endpoint http://192.168.1.11:7070 --region us-east-1 --bucket rdma --key cuobjtest-object
SUCCESS: RDMA GET transferred 4194304 bytes
SHA256:  4fde9d0466110d580b80deceabb869ba25676288f780a7fe0623bae687e49c6a
Target:  rdma-download.bin

$ python3 test-rdma-client.py opensharing-table --memory host --share report-share --schema report-schema --table report_table --file-id tables/test-object.parquet
SUCCESS: RDMA GET transferred 3220 bytes
SHA256:  a40a1a024c1ff5313f8549d3174201f65dd55c50f45712a94d9a4857524b152b
Target:  rdma-table-download.parquet
```

In this last step, notice `--memory host`. This is the S3/RDMA approach for users without GPU hardware, meant for compatibility testing (mentioned [here](https://scaleoutsean.github.io/2026/08/08/versity-s3-rdma-with-netapp-eseries.html#appendix-a-vgw-s3rdma-backed-by-e-series-nvmeroce) as well).

My S3/RDMA client wraps the host-memory client built with "`make cuobjtest-host`". You can use "`make cuobjtest-gpu`" and wrap that if you have GPU hardware. See the [Versity S3/RDMA User Guide](https://github.com/versity/versitygw/wiki/RDMA-User#building) for more.

## Contributions

This is a demo project with closed source and contributions are not accepted. 

Create an issue if the instructions or Compose stack do not work as documented.

## Privacy 

*OpenSharing API Server for NetApp StorageGRID and Versity S3 Gateway* doesn't collect, send, or share any telemetry or other data outside of the expected (to servers and client from included Docker Compose stack).

Please check 3rd party containers for their individual privacy policies. 

## License 

Binary builds of OpenSharing Server for StorageGRID and Versity Gateway are freely available.

- Code: `docker-compose.yaml`, `test-client.py` and container configuration files: MIT License 
- Documentation: CC BY 4.0
