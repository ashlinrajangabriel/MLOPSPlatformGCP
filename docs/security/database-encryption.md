# Database Encryption Configuration

## Overview
The MLflow deployment uses Google Cloud SQL with customer-managed encryption keys (CMEK) for enhanced security. This document outlines the encryption configuration and key management setup.

## Encryption Configuration

### Cloud SQL Encryption
The Cloud SQL instance is configured with a customer-managed encryption key (CMEK) for data-at-rest encryption. This provides an additional layer of security beyond Google Cloud's default encryption.

```hcl
resource "google_sql_database_instance" "mlflow" {
  encryption_key_name = google_kms_crypto_key.sql.id
  # ... other configuration
}
```

### Key Management System (KMS) Configuration

#### KMS Keyring
A dedicated keyring is created for MLflow's encryption keys:
```hcl
resource "google_kms_key_ring" "mlflow" {
  name     = "mlflow-keyring"
  location = var.region
}
```

#### Cloud SQL Encryption Key
The encryption key for Cloud SQL has the following specifications:
- **Name**: mlflow-sql-key
- **Rotation Period**: 90 days (7776000 seconds)
- **Algorithm**: GOOGLE_SYMMETRIC_ENCRYPTION
- **Protection Level**: SOFTWARE
- **Lifecycle**: Protected against accidental deletion

```hcl
resource "google_kms_crypto_key" "sql" {
  name            = "mlflow-sql-key"
  key_ring        = google_kms_key_ring.mlflow.id
  rotation_period = "7776000s"
  
  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}
```

### IAM Permissions
The Cloud SQL service account is granted the necessary permissions to use the encryption key:
```hcl
resource "google_kms_crypto_key_iam_member" "sql" {
  crypto_key_id = google_kms_crypto_key.sql.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_sql_database_instance.mlflow.service_account_email_address}"
}
```

## Security Benefits

1. **Enhanced Control**: Customer-managed encryption keys provide greater control over data encryption and access.
2. **Regular Key Rotation**: Automatic key rotation every 90 days enhances security.
3. **Deletion Protection**: The `prevent_destroy` lifecycle rule protects against accidental key deletion.
4. **Audit Trail**: All key usage and rotation events are logged for audit purposes.
5. **Compliance**: Helps meet compliance requirements for data encryption and key management.

## Best Practices

1. Monitor KMS key usage and rotation events in Cloud Audit Logs
2. Regularly review IAM permissions for the encryption keys
3. Maintain backup procedures for key material
4. Document and test key rotation procedures
5. Ensure proper access controls to the KMS keyring and keys 