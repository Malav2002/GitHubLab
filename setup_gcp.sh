#!/usr/bin/env bash
# setup_gcp.sh — Provisions all GCP resources needed for GitHubLab
# Usage: ./setup_gcp.sh
# Edit the variables below before running.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-}"          # set env var or hardcode here
BUCKET_NAME="${GCS_BUCKET_NAME:-}"        # e.g. my-ml-models-bucket
REGION="${REGION:-us-east4}"
REPOSITORY_NAME="my-repo"
SA_NAME="github-actions-sa"
VERSION_FILE_NAME="${VERSION_FILE_NAME:-version.txt}"
KEY_FILE="sa-key.json"
# ──────────────────────────────────────────────────────────────────────────────

# ── Validate required vars ────────────────────────────────────────────────────
if [[ -z "$PROJECT_ID" ]]; then
  echo "ERROR: Set GCP_PROJECT_ID environment variable or edit PROJECT_ID in this script."
  exit 1
fi
if [[ -z "$BUCKET_NAME" ]]; then
  echo "ERROR: Set GCS_BUCKET_NAME environment variable or edit BUCKET_NAME in this script."
  exit 1
fi

SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "========================================"
echo " GitHubLab GCP Setup"
echo "========================================"
echo " Project  : $PROJECT_ID"
echo " Bucket   : $BUCKET_NAME"
echo " Region   : $REGION"
echo " SA email : $SA_EMAIL"
echo "========================================"

# ── 1. Set active project ─────────────────────────────────────────────────────
echo ""
echo "[1/6] Setting active project..."
gcloud config set project "$PROJECT_ID"

# ── 2. Enable APIs ────────────────────────────────────────────────────────────
echo ""
echo "[2/6] Enabling required APIs..."
gcloud services enable \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com

# ── 3. Create GCS bucket ──────────────────────────────────────────────────────
echo ""
echo "[3/6] Creating GCS bucket gs://$BUCKET_NAME ..."
if gsutil ls "gs://$BUCKET_NAME" &>/dev/null; then
  echo "  Bucket already exists — skipping."
else
  gsutil mb -l "$REGION" "gs://$BUCKET_NAME"
  echo "  Bucket created."
fi

# ── 4. Create Artifact Registry repository ───────────────────────────────────
echo ""
echo "[4/6] Creating Artifact Registry repository '$REPOSITORY_NAME' in $REGION..."
if gcloud artifacts repositories describe "$REPOSITORY_NAME" --location="$REGION" &>/dev/null; then
  echo "  Repository already exists — skipping."
else
  gcloud artifacts repositories create "$REPOSITORY_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="ML model Docker images"
  echo "  Repository created."
fi

# ── 5. Create service account & grant roles ───────────────────────────────────
echo ""
echo "[5/6] Setting up service account $SA_NAME..."

if gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
  echo "  Service account already exists — skipping creation."
else
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Service Account"
  echo "  Service account created."
fi

echo "  Granting roles/storage.admin..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin" \
  --condition=None \
  --quiet

echo "  Granting roles/artifactregistry.writer..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer" \
  --condition=None \
  --quiet

# ── 6. Export service account key ────────────────────────────────────────────
echo ""
echo "[6/6] Exporting service account key to $KEY_FILE..."
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="$SA_EMAIL"

echo ""
echo "========================================"
echo " Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Add the following secrets to your GitHub repository"
echo "     (Settings → Secrets and variables → Actions):"
echo ""
echo "     GCP_SA_KEY          → contents of $KEY_FILE"
echo "     GCP_PROJECT_ID      → $PROJECT_ID"
echo "     GCS_BUCKET_NAME     → $BUCKET_NAME"
echo "     VERSION_FILE_NAME   → $VERSION_FILE_NAME"
echo ""
echo "  2. Push to the 'main' branch to trigger the pipeline."
echo ""
echo "  IMPORTANT: Do NOT commit $KEY_FILE — it is already in .gitignore."
echo ""
