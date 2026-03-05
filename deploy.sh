#!/usr/bin/env bash
set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
# Create a globally unique bucket name by appending the project id
BUCKET_NAME="gemini-tracker-data-${PROJECT_ID}"
JOB_NAME="gemini-deprecation-tracker"
SCHEDULER_JOB_NAME="gemini-tracker-daily"

SA_RUN="gemini-tracker-sa"
SA_INVOKER="gemini-tracker-invoker"

echo "=========================================================="
echo "Deploying Gemini Deprecation Tracker to Google Cloud"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Bucket: $BUCKET_NAME"
echo "=========================================================="
echo ""

# 1. Enable necessary APIs
echo "[1/7] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    iam.googleapis.com

# 2. Create the GCS Bucket
echo "[2/7] Checking for GCS Bucket: gs://$BUCKET_NAME"
# Note: ignoring errors on ls in case bucket doesn't exist yet
if ! gcloud storage ls "gs://$BUCKET_NAME" >/dev/null 2>&1; then
    echo "      Creating bucket gs://$BUCKET_NAME..."
    gcloud storage buckets create "gs://$BUCKET_NAME" --location="$REGION" --uniform-bucket-level-access
else
    echo "      Bucket already exists."
fi

echo "      Making bucket contents publicly readable..."
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
    --member="allUsers" \
    --role="roles/storage.objectViewer" >/dev/null

# 3. Create Cloud Run Service Account and grant Storage permissions
echo "[3/7] Setting up Cloud Run Service Account ($SA_RUN)..."
if ! gcloud iam service-accounts describe "${SA_RUN}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${SA_RUN}" \
        --display-name="SA for Gemini Tracker Cloud Run Job"
    echo "      Waiting 10 seconds for service account to propagate by GCP..."
    sleep 10
fi

echo "      Granting Storage Object Admin to ${SA_RUN} on bucket ${BUCKET_NAME}..."
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
    --member="serviceAccount:${SA_RUN}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin" >/dev/null

# 4. Deploy Cloud Run Job
echo "[4/7] Deploying Cloud Run Job ($JOB_NAME)..."
echo "      (This will securely build the container using Cloud Build and deploy it.)"
gcloud run jobs deploy "$JOB_NAME" \
    --source . \
    --region "$REGION" \
    --service-account "${SA_RUN}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars "GCS_BUCKET=$BUCKET_NAME" \
    --max-retries 1 \
    --task-timeout 5m

# 5. Create Cloud Scheduler Invoker Service Account
echo "[5/7] Setting up Cloud Scheduler Service Account ($SA_INVOKER)..."
if ! gcloud iam service-accounts describe "${SA_INVOKER}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${SA_INVOKER}" \
        --display-name="SA for Cloud Scheduler to invoke Gemini Tracker"
    echo "      Waiting 10 seconds for service account to propagate by GCP..."
    sleep 10
fi

# 6. Grant Run Invoker to Scheduler SA
echo "[6/7] Granting Run Invoker to ${SA_INVOKER}..."
gcloud run jobs add-iam-policy-binding "$JOB_NAME" \
    --region="$REGION" \
    --member="serviceAccount:${SA_INVOKER}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" >/dev/null

# 7. Create/Update Cloud Scheduler Job
echo "[7/7] Configuring Cloud Scheduler Trigger ($SCHEDULER_JOB_NAME)..."
# Try to create, if it exists update it.
if ! gcloud scheduler jobs describe "$SCHEDULER_JOB_NAME" --location="$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs create http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="0 10 * * *" \
        --time-zone="Etc/UTC" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method="POST" \
        --oauth-service-account-email="${SA_INVOKER}@${PROJECT_ID}.iam.gserviceaccount.com"
else
    gcloud scheduler jobs update http "$SCHEDULER_JOB_NAME" \
        --location="$REGION" \
        --schedule="0 10 * * *" \
        --time-zone="Etc/UTC" \
        --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
        --http-method="POST" \
        --oauth-service-account-email="${SA_INVOKER}@${PROJECT_ID}.iam.gserviceaccount.com"
fi

echo "=========================================================="
echo "✅ Deployment Complete!"
echo "You can trigger a manual run with:"
echo "gcloud run jobs execute $JOB_NAME --region $REGION"
echo "=========================================================="
