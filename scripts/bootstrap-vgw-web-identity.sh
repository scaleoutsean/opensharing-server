#!/bin/sh
set -eu

provider_arn="arn:aws:iam::000000000000:oidc-provider/${OIDC_PROVIDER_URL}"

if ! aws --endpoint-url "$IAM_ENDPOINT" iam get-open-id-connect-provider \
    --open-id-connect-provider-arn "$provider_arn" >/dev/null 2>&1; then
    aws --endpoint-url "$IAM_ENDPOINT" iam create-open-id-connect-provider \
        --url "$OIDC_PROVIDER_URL" \
        --client-id-list "$OIDC_CLIENT_ID"
fi

cat >/tmp/trust-policy.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"${provider_arn}"},"Action":"sts:AssumeRoleWithWebIdentity"}]}
EOF

if ! aws --endpoint-url "$IAM_ENDPOINT" iam get-role \
    --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    aws --endpoint-url "$IAM_ENDPOINT" iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/trust-policy.json
fi

cat >/tmp/base-s3-read.json <<'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:ListBucket","s3:GetObject"],"Resource":["arn:aws:s3:::*"]}]}
EOF

aws --endpoint-url "$IAM_ENDPOINT" iam put-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-name base-s3-read \
    --policy-document file:///tmp/base-s3-read.json