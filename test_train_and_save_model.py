import pytest
from unittest.mock import patch, MagicMock
from train_and_save_model import (
    download_data,
    preprocess_data,
    train_model,
    get_model_version,
    update_model_version,
    save_model_to_gcs,
)


# --- download_data ---

def test_download_data_shape():
    features, target = download_data()
    # Wine dataset: 178 samples, 13 features, 3 classes
    assert features.shape == (178, 13)
    assert target.shape == (178,)
    assert set(target.unique()) == {0, 1, 2}


# --- preprocess_data ---

def test_preprocess_data_split():
    features, target = download_data()
    X_train, X_test, y_train, y_test = preprocess_data(features, target)
    total = len(features)
    assert len(X_test) == pytest.approx(total * 0.2, abs=2)
    assert len(X_train) + len(X_test) == total


# --- train_model ---

def test_train_model_returns_fitted_model():
    features, target = download_data()
    X_train, X_test, y_train, y_test = preprocess_data(features, target)
    model = train_model(X_train, y_train)
    # GradientBoostingClassifier exposes n_estimators_ after fitting
    assert hasattr(model, "n_estimators_")
    preds = model.predict(X_test)
    assert len(preds) == len(X_test)


# --- get_model_version ---

def test_get_model_version_blob_exists():
    with patch('train_and_save_model.storage.Client') as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = "3"

        version = get_model_version("test-bucket", "version.txt")
        assert version == 3


def test_get_model_version_blob_missing():
    with patch('train_and_save_model.storage.Client') as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        mock_blob.exists.return_value = False  # Blob does not exist

        version = get_model_version("test-bucket", "version.txt")
        assert version == 0


# --- update_model_version ---

def test_update_model_version_success():
    with patch('train_and_save_model.storage.Client') as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        result = update_model_version("test-bucket", "version.txt", 5)
        assert result is True
        mock_blob.upload_from_string.assert_called_once_with("5")


def test_update_model_version_invalid_type():
    with pytest.raises(ValueError, match="Version must be an integer"):
        update_model_version("test-bucket", "version.txt", "not-an-int")


def test_update_model_version_gcs_error():
    with patch('train_and_save_model.storage.Client') as mock_client:
        mock_client.side_effect = Exception("GCS connection failed")
        result = update_model_version("test-bucket", "version.txt", 1)
        assert result is False


# --- save_model_to_gcs ---

def test_save_model_to_gcs():
    with patch('train_and_save_model.storage.Client') as mock_client, \
         patch('train_and_save_model.joblib.dump') as mock_dump, \
         patch('train_and_save_model.ensure_folder_exists') as mock_ensure:

        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        features, target = download_data()
        X_train, X_test, y_train, y_test = preprocess_data(features, target)
        model = train_model(X_train, y_train)

        save_model_to_gcs(model, "test-bucket", "trained_models/model_v1.joblib")

        mock_dump.assert_called_once_with(model, "model.joblib")
        mock_ensure.assert_called_once()
        mock_blob.upload_from_filename.assert_called_once_with("model.joblib")
