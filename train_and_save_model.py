import os
from dotenv import load_dotenv

# Load environment variables from a .env file located in the same directory as this script
load_dotenv()

# Retrieve the values of environment variables defined in the .env file
BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')       # Google Cloud Storage bucket name
VERSION_FILE_NAME = os.getenv('VERSION_FILE_NAME') # Name of the file where the model version is stored

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from google.cloud import storage
import joblib
from datetime import datetime

# Function to download the Wine dataset from the sklearn library
def download_data():
    from sklearn.datasets import load_wine
    wine = load_wine()  # Load the Wine dataset (modification: Iris → Wine)
    features = pd.DataFrame(wine.data, columns=wine.feature_names)
    target = pd.Series(wine.target)
    return features, target

# Function to preprocess the downloaded data by splitting it into training and testing sets
def preprocess_data(X, y):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    return X_train, X_test, y_train, y_test

# Function to train a GradientBoosting model using the preprocessed training data
# (modification: RandomForest → GradientBoostingClassifier)
def train_model(X_train, y_train):
    model = GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)
    return model

# Function to retrieve the current model version from Google Cloud Storage
def get_model_version(bucket_name, version_file_name):
    storage_client = storage.Client()         # Create a GCP Storage client
    bucket = storage_client.bucket(bucket_name)  # Access the specified bucket
    blob = bucket.blob(version_file_name)     # Access the specified blob within the bucket

    if blob.exists():
        version_as_string = blob.download_as_text()  # Retrieve the version number as text
        version = int(version_as_string)              # Convert the version number to an integer
    else:
        version = 0  # If the blob does not exist, start at version 0
    return version

# Function to update the model version in Google Cloud Storage
def update_model_version(bucket_name, version_file_name, version):
    if not isinstance(version, int):
        raise ValueError("Version must be an integer")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(version_file_name)
        blob.upload_from_string(str(version))  # Upload the new version number as a string
        return True
    except Exception as e:
        print(f"Error updating model version: {e}")
        return False

# Function to ensure that a specific folder exists within a bucket in Google Cloud Storage
def ensure_folder_exists(bucket, folder_name):
    blob = bucket.blob(f"{folder_name}/")
    if not blob.exists():
        blob.upload_from_string('')  # Create folder by uploading an empty string
        print(f"Created folder: {folder_name}")

# Function to save the trained model both locally and to Google Cloud Storage
def save_model_to_gcs(model, bucket_name, blob_name):
    joblib.dump(model, "model.joblib")  # Save the model locally using joblib

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    ensure_folder_exists(bucket, "trained_models")

    blob = bucket.blob(blob_name)
    blob.upload_from_filename('model.joblib')  # Upload the locally saved model to GCS

# Main function that orchestrates downloading data, training the model, and saving it
def main():
    # Retrieve and increment model version
    current_version = get_model_version(BUCKET_NAME, VERSION_FILE_NAME)
    new_version = current_version + 1

    # Download and preprocess data
    X, y = download_data()
    X_train, X_test, y_train, y_test = preprocess_data(X, y)

    # Train and evaluate the model
    model = train_model(X_train, y_train)
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy: {accuracy:.4f}")

    # Print per-class metrics (modification: added classification report)
    from sklearn.datasets import load_wine
    wine = load_wine()
    report = classification_report(y_test, y_pred, target_names=wine.target_names)
    print(f"Classification Report:\n{report}")

    # Save the model with a new version and timestamp in GCS
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    blob_name = f"trained_models/model_v{new_version}_{timestamp}.joblib"
    save_model_to_gcs(model, BUCKET_NAME, blob_name)
    print(f"Model saved to gs://{BUCKET_NAME}/{blob_name}")

    # Update the model version in GCS if saving was successful
    if update_model_version(BUCKET_NAME, VERSION_FILE_NAME, new_version):
        print(f"Model version updated to {new_version}")
        print(f"MODEL_VERSION_OUTPUT: {new_version}")
    else:
        print("Failed to update model version")

# Conditional to ensure the main function runs only if the script is executed directly
if __name__ == "__main__":
    main()
