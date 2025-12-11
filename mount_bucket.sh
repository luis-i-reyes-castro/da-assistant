#!/usr/bin/env bash
#
# Mounts the DigitalOcean Spaces Bucket defined in .env;
# unmount later with:
#   fusermount -u <mount-point>

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
MOUNT_POINT="${1:-$ROOT_DIR/kgstorage}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Cannot find .env at $ENV_FILE" >&2
  exit 1
fi

# Load SPACES_* variables from the repo's .env file.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

: "${SPACES_BUCKET:?Set SPACES_BUCKET in .env}"
: "${SPACES_REGION:?Set SPACES_REGION in .env}"
: "${SPACES_KEY_ID:?Set SPACES_KEY_ID in .env}"
: "${SPACES_KEY_SECRET:?Set SPACES_KEY_SECRET in .env}"

mkdir -p "$MOUNT_POINT"

export AWS_ACCESS_KEY_ID="$SPACES_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$SPACES_KEY_SECRET"
export AWS_REGION="$SPACES_REGION"
export AWS_ENDPOINT_URL="https://${SPACES_REGION}.digitaloceanspaces.com"

echo "Mounting bucket '$SPACES_BUCKET' to $MOUNT_POINT"
echo "Using endpoint $AWS_ENDPOINT_URL"

ALLOW_OTHER_FLAG=()
if grep -qE '^[[:space:]]*user_allow_other' /etc/fuse.conf 2>/dev/null; then
  ALLOW_OTHER_FLAG=(--allow-other)
else
  echo "Note: /etc/fuse.conf lacks 'user_allow_other'; mounting without --allow-other."
fi

exec mount-s3 \
  "${ALLOW_OTHER_FLAG[@]}" \
  --endpoint-url "$AWS_ENDPOINT_URL" \
  "$SPACES_BUCKET" \
  "$MOUNT_POINT"
