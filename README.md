# GitHubLab — ML Model Training & CI/CD Pipeline on GCP

A production-style MLOps pipeline that trains a Wine classification model, versions and stores artifacts in Google Cloud Storage, and automatically builds & pushes a containerized image to Google Artifact Registry — all triggered by a push to `main` via GitHub Actions.

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [GCP Setup](#gcp-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Local Development](#local-development)
- [Running Tests](#running-tests)
- [CI/CD Pipeline](#cicd-pipeline)
- [Model Artifacts](#model-artifacts)

---

## Architecture

```
Push to main
     │
     ▼
GitHub Actions
     │
     ├─► Run pytest
     │
     ├─► Authenticate with GCP (Service Account)
     │
     ├─► Train GradientBoostingClassifier
     │        └─► Save model.joblib to GCS (versioned)
     │        └─► Update version counter in GCS
     │
     └─► Build Docker image
              └─► Push to Artifact Registry
                       ├─► model-image:v{N}
                       └─► model-image:latest
```

---

## Project Structure

```
GitHubLab/
├── .github/
│   └── workflows/
│       └── ci_cd.yml               # GitHub Actions pipeline
├── train_and_save_model.py         # Core ML training script
├── test_train_and_save_model.py    # Unit tests (pytest)
├── Dockerfile                      # Container definition
├── requirements.txt                # Pinned Python dependencies
└── .gitignore
```

---

## How It Works

1. **Data** — Loads the scikit-learn Wine dataset (178 samples, 13 features, 3 classes).
2. **Training** — Fits a `GradientBoostingClassifier` (100 estimators, lr=0.1) on an 80/20 split.
3. **Versioning** — Reads the current model version from a text file in GCS, increments it, and writes it back after a successful save.
4. **Artifact Storage** — Saves `model.joblib` to:
   ```
   gs://<BUCKET_NAME>/trained_models/model_v{N}_{timestamp}.joblib
   ```
5. **Containerization** — Packages the training script into a Python 3.10-slim Docker image.
6. **Registry** — Pushes the image to Artifact Registry with two tags:
   ```
   us-east4-docker.pkg.dev/<PROJECT_ID>/my-repo/model-image:{N}
   us-east4-docker.pkg.dev/<PROJECT_ID>/my-repo/model-image:latest
   ```

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Docker | 20+ |
| Google Cloud SDK (`gcloud`) | Latest |
| GitHub repository | With Actions enabled |

---

## GCP Setup

Run the helper script to provision all required GCP resources:

```bash
chmod +x setup_gcp.sh
./setup_gcp.sh
```

Or follow the manual steps below.

### 1. Set your project

```bash
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID
```

### 2. Enable required APIs

```bash
gcloud services enable \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com
```

### 3. Create a GCS bucket

```bash
export BUCKET_NAME="your-model-bucket-name"
export REGION="us-east4"

gsutil mb -l $REGION gs://$BUCKET_NAME
```

### 4. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create my-repo \
  --repository-format=docker \
  --location=$REGION \
  --description="ML model Docker images"
```

### 5. Create a service account and grant permissions

```bash
export SA_NAME="github-actions-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Create service account
gcloud iam service-accounts create $SA_NAME \
  --display-name="GitHub Actions Service Account"

# Grant GCS permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

# Grant Artifact Registry permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"

# Export the key
gcloud iam service-accounts keys create sa-key.json \
  --iam-account=$SA_EMAIL
```

> **Important:** Never commit `sa-key.json` to version control. It is listed in `.gitignore`.

---

## GitHub Secrets Configuration

Navigate to your repository → **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `GCP_SA_KEY` | Contents of `sa-key.json` (the entire JSON) |
| `GCP_PROJECT_ID` | Your GCP project ID |
| `GCS_BUCKET_NAME` | Name of the GCS bucket you created |
| `VERSION_FILE_NAME` | e.g. `version.txt` |

---

## Local Development

### 1. Clone and create a virtual environment

```bash
git clone <your-repo-url>
cd GitHubLab

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create a `.env` file

```bash
# .env  (never commit this)
GCS_BUCKET_NAME=your-bucket-name
VERSION_FILE_NAME=version.txt
```

### 3. Authenticate with GCP locally

```bash
gcloud auth application-default login
# or point to your service account key:
export GOOGLE_APPLICATION_CREDENTIALS="sa-key.json"
```

### 4. Run training locally

```bash
python train_and_save_model.py
```

Expected output:
```
Model accuracy: 0.9722
Classification Report:
              precision    recall  f1-score ...
MODEL_VERSION_OUTPUT: 1
```

---

## Running Tests

```bash
pytest test_train_and_save_model.py -v
```

Tests cover:
- Dataset shape validation
- Train/test split correctness
- Model training and prediction
- GCS version read/write (mocked)
- Model save to GCS (mocked)

---

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci_cd.yml`) runs on every push or PR to `main`:

| Step | Description |
|------|-------------|
| Checkout | Pulls the latest code |
| Python 3.10 | Sets up the runtime with pip cache |
| Install deps | `pip install -r requirements.txt` |
| Run tests | `pytest test_train_and_save_model.py -v` |
| Auth GCP | Authenticates via `GCP_SA_KEY` secret |
| Cloud SDK | Installs `gcloud` CLI |
| Docker auth | Configures Docker for Artifact Registry |
| Train model | Runs `train_and_save_model.py`, captures version |
| Build & push | Builds image, pushes with version tag + `latest` |

---

## Model Artifacts

### GCS Layout

```
gs://<BUCKET_NAME>/
├── trained_models/
│   ├── model_v1_20240410120000.joblib
│   ├── model_v2_20240411083012.joblib
│   └── ...
└── version.txt   ← current version number
```

### Artifact Registry Layout

```
us-east4-docker.pkg.dev/<PROJECT_ID>/my-repo/
└── model-image
    ├── :1        ← versioned tag
    ├── :2
    └── :latest   ← always points to the newest
```

### Pull and run the latest image

```bash
docker pull us-east4-docker.pkg.dev/<PROJECT_ID>/my-repo/model-image:latest
docker run --rm \
  -e GCS_BUCKET_NAME=<BUCKET_NAME> \
  -e VERSION_FILE_NAME=version.txt \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds/sa-key.json \
  -v $(pwd)/sa-key.json:/creds/sa-key.json \
  us-east4-docker.pkg.dev/<PROJECT_ID>/my-repo/model-image:latest
```
