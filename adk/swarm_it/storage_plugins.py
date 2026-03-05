"""
Storage Plugins - Phase 6 Extensibility

Implements pluggable storage backends for evidence and certificates:
- AWS S3 storage
- Google Cloud Storage (GCS)
- Azure Blob Storage
- Local filesystem (default)

Based on ExtensibilityArchitect recommendation:
"Need pluggable storage for evidence export to support multi-cloud deployments."

Implements:
- StorageProvider abstract base class
- S3StorageProvider
- GCSStorageProvider
- AzureBlobStorageProvider
- LocalStorageProvider
- StorageRegistry for plugin discovery

Usage:
    from swarm_it_adk.storage_plugins import S3StorageProvider

    # Configure S3 storage
    storage = S3StorageProvider(
        bucket_name="rsct-evidence",
        region_name="us-east-1",
        prefix="prod/"
    )

    # Store evidence
    storage.store_evidence(evidence_id, evidence_data)

    # Retrieve evidence
    evidence = storage.retrieve_evidence(evidence_id)
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path


class StorageType(str, Enum):
    """Storage provider types."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


@dataclass
class StorageConfig:
    """Storage configuration."""
    storage_type: StorageType
    # Provider-specific config
    config: Dict[str, Any]


class StorageProvider(ABC):
    """
    Abstract base class for storage providers.

    Subclasses implement specific storage backends.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize storage provider.

        Args:
            config: Provider-specific configuration
        """
        self.config = config or {}

    @abstractmethod
    def store_evidence(
        self,
        evidence_id: str,
        evidence_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store evidence.

        Args:
            evidence_id: Unique evidence identifier
            evidence_data: Evidence data to store
            metadata: Optional metadata

        Returns:
            Storage location (URL, path, etc.)
        """
        pass

    @abstractmethod
    def retrieve_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve evidence.

        Args:
            evidence_id: Evidence identifier

        Returns:
            Evidence data or None if not found
        """
        pass

    @abstractmethod
    def delete_evidence(self, evidence_id: str) -> bool:
        """
        Delete evidence.

        Args:
            evidence_id: Evidence identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_evidence(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """
        List evidence IDs.

        Args:
            prefix: Optional prefix filter
            limit: Maximum number of results

        Returns:
            List of evidence IDs
        """
        pass

    def store_certificate(
        self,
        certificate_id: str,
        certificate_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store certificate (delegates to store_evidence).

        Args:
            certificate_id: Certificate identifier
            certificate_data: Certificate data
            metadata: Optional metadata

        Returns:
            Storage location
        """
        return self.store_evidence(certificate_id, certificate_data, metadata)

    def retrieve_certificate(self, certificate_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve certificate (delegates to retrieve_evidence).

        Args:
            certificate_id: Certificate identifier

        Returns:
            Certificate data or None
        """
        return self.retrieve_evidence(certificate_id)


class LocalStorageProvider(StorageProvider):
    """
    Local filesystem storage provider.

    Default provider, stores evidence as JSON files.
    """

    def __init__(
        self,
        base_path: str = "evidence",
        create_dirs: bool = True
    ):
        """
        Initialize local storage.

        Args:
            base_path: Base directory for storage
            create_dirs: Whether to create directories
        """
        super().__init__({"base_path": base_path})
        self.base_path = Path(base_path)

        if create_dirs:
            self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, evidence_id: str) -> Path:
        """Get file path for evidence ID."""
        # Sanitize evidence_id
        safe_id = evidence_id.replace("/", "_").replace("\\", "_")
        return self.base_path / f"{safe_id}.json"

    def store_evidence(
        self,
        evidence_id: str,
        evidence_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store evidence to local file."""
        file_path = self._get_file_path(evidence_id)

        # Add metadata
        data = {
            "evidence_id": evidence_id,
            "evidence": evidence_data,
            "metadata": metadata or {},
            "stored_at": datetime.utcnow().isoformat()
        }

        # Write JSON file
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        return str(file_path)

    def retrieve_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence from local file."""
        file_path = self._get_file_path(evidence_id)

        if not file_path.exists():
            return None

        with open(file_path, "r") as f:
            data = json.load(f)

        return data.get("evidence")

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence file."""
        file_path = self._get_file_path(evidence_id)

        if not file_path.exists():
            return False

        file_path.unlink()
        return True

    def list_evidence(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """List evidence files."""
        pattern = f"{prefix}*.json" if prefix else "*.json"
        files = list(self.base_path.glob(pattern))[:limit]

        # Extract evidence IDs
        evidence_ids = [f.stem for f in files]
        return evidence_ids


class S3StorageProvider(StorageProvider):
    """
    AWS S3 storage provider.

    Stores evidence in S3 bucket.
    """

    def __init__(
        self,
        bucket_name: str,
        region_name: str = "us-east-1",
        prefix: str = "",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        Initialize S3 storage.

        Args:
            bucket_name: S3 bucket name
            region_name: AWS region
            prefix: Key prefix (e.g., "evidence/")
            aws_access_key_id: AWS access key (optional, uses IAM role if None)
            aws_secret_access_key: AWS secret key (optional)
        """
        super().__init__({
            "bucket_name": bucket_name,
            "region_name": region_name,
            "prefix": prefix
        })

        try:
            import boto3
            self.s3_available = True
        except ImportError:
            self.s3_available = False
            raise ImportError(
                "boto3 not installed. Install with: pip install boto3"
            )

        # Create S3 client
        session_kwargs = {"region_name": region_name}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key
            })

        session = boto3.Session(**session_kwargs)
        self.s3 = session.client("s3")
        self.bucket_name = bucket_name
        self.prefix = prefix

    def _get_s3_key(self, evidence_id: str) -> str:
        """Get S3 key for evidence ID."""
        return f"{self.prefix}{evidence_id}.json"

    def store_evidence(
        self,
        evidence_id: str,
        evidence_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store evidence to S3."""
        key = self._get_s3_key(evidence_id)

        # Prepare data
        data = {
            "evidence_id": evidence_id,
            "evidence": evidence_data,
            "metadata": metadata or {},
            "stored_at": datetime.utcnow().isoformat()
        }

        # Upload to S3
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=json.dumps(data, indent=2),
            ContentType="application/json",
            Metadata=metadata or {}
        )

        return f"s3://{self.bucket_name}/{key}"

    def retrieve_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence from S3."""
        key = self._get_s3_key(evidence_id)

        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            data = json.loads(response["Body"].read())
            return data.get("evidence")
        except self.s3.exceptions.NoSuchKey:
            return None

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence from S3."""
        key = self._get_s3_key(evidence_id)

        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False

    def list_evidence(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """List evidence in S3."""
        list_prefix = f"{self.prefix}{prefix}" if prefix else self.prefix

        response = self.s3.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=list_prefix,
            MaxKeys=limit
        )

        if "Contents" not in response:
            return []

        # Extract evidence IDs
        evidence_ids = []
        for obj in response["Contents"]:
            key = obj["Key"]
            # Remove prefix and .json extension
            evidence_id = key[len(self.prefix):].replace(".json", "")
            evidence_ids.append(evidence_id)

        return evidence_ids


class GCSStorageProvider(StorageProvider):
    """
    Google Cloud Storage provider.

    Stores evidence in GCS bucket.
    """

    def __init__(
        self,
        bucket_name: str,
        prefix: str = "",
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCS storage.

        Args:
            bucket_name: GCS bucket name
            prefix: Blob prefix
            credentials_path: Path to service account JSON (optional)
        """
        super().__init__({
            "bucket_name": bucket_name,
            "prefix": prefix
        })

        try:
            from google.cloud import storage
            self.gcs_available = True
        except ImportError:
            self.gcs_available = False
            raise ImportError(
                "google-cloud-storage not installed. "
                "Install with: pip install google-cloud-storage"
            )

        # Create GCS client
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix

    def _get_blob_name(self, evidence_id: str) -> str:
        """Get blob name for evidence ID."""
        return f"{self.prefix}{evidence_id}.json"

    def store_evidence(
        self,
        evidence_id: str,
        evidence_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store evidence to GCS."""
        blob_name = self._get_blob_name(evidence_id)
        blob = self.bucket.blob(blob_name)

        # Prepare data
        data = {
            "evidence_id": evidence_id,
            "evidence": evidence_data,
            "metadata": metadata or {},
            "stored_at": datetime.utcnow().isoformat()
        }

        # Upload to GCS
        blob.upload_from_string(
            json.dumps(data, indent=2),
            content_type="application/json"
        )

        # Set metadata
        if metadata:
            blob.metadata = metadata
            blob.patch()

        return f"gs://{self.bucket.name}/{blob_name}"

    def retrieve_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence from GCS."""
        blob_name = self._get_blob_name(evidence_id)
        blob = self.bucket.blob(blob_name)

        if not blob.exists():
            return None

        data = json.loads(blob.download_as_text())
        return data.get("evidence")

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence from GCS."""
        blob_name = self._get_blob_name(evidence_id)
        blob = self.bucket.blob(blob_name)

        if not blob.exists():
            return False

        blob.delete()
        return True

    def list_evidence(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """List evidence in GCS."""
        list_prefix = f"{self.prefix}{prefix}" if prefix else self.prefix

        blobs = self.client.list_blobs(
            self.bucket,
            prefix=list_prefix,
            max_results=limit
        )

        # Extract evidence IDs
        evidence_ids = []
        for blob in blobs:
            # Remove prefix and .json extension
            evidence_id = blob.name[len(self.prefix):].replace(".json", "")
            evidence_ids.append(evidence_id)

        return evidence_ids


class AzureBlobStorageProvider(StorageProvider):
    """
    Azure Blob Storage provider.

    Stores evidence in Azure Blob container.
    """

    def __init__(
        self,
        container_name: str,
        connection_string: Optional[str] = None,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        prefix: str = ""
    ):
        """
        Initialize Azure Blob storage.

        Args:
            container_name: Container name
            connection_string: Connection string (optional)
            account_name: Storage account name (optional)
            account_key: Storage account key (optional)
            prefix: Blob prefix
        """
        super().__init__({
            "container_name": container_name,
            "prefix": prefix
        })

        try:
            from azure.storage.blob import BlobServiceClient
            self.azure_available = True
        except ImportError:
            self.azure_available = False
            raise ImportError(
                "azure-storage-blob not installed. "
                "Install with: pip install azure-storage-blob"
            )

        # Create blob service client
        if connection_string:
            self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        elif account_name and account_key:
            self.blob_service = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=account_key
            )
        else:
            raise ValueError("Must provide connection_string or account_name + account_key")

        self.container_client = self.blob_service.get_container_client(container_name)
        self.prefix = prefix

    def _get_blob_name(self, evidence_id: str) -> str:
        """Get blob name for evidence ID."""
        return f"{self.prefix}{evidence_id}.json"

    def store_evidence(
        self,
        evidence_id: str,
        evidence_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store evidence to Azure Blob."""
        blob_name = self._get_blob_name(evidence_id)
        blob_client = self.container_client.get_blob_client(blob_name)

        # Prepare data
        data = {
            "evidence_id": evidence_id,
            "evidence": evidence_data,
            "metadata": metadata or {},
            "stored_at": datetime.utcnow().isoformat()
        }

        # Upload to Azure
        blob_client.upload_blob(
            json.dumps(data, indent=2),
            overwrite=True,
            content_settings={"content_type": "application/json"},
            metadata=metadata
        )

        return f"https://{self.blob_service.account_name}.blob.core.windows.net/{self.container_client.container_name}/{blob_name}"

    def retrieve_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve evidence from Azure Blob."""
        blob_name = self._get_blob_name(evidence_id)
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            data = json.loads(blob_client.download_blob().readall())
            return data.get("evidence")
        except Exception:
            return None

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence from Azure Blob."""
        blob_name = self._get_blob_name(evidence_id)
        blob_client = self.container_client.get_blob_client(blob_name)

        try:
            blob_client.delete_blob()
            return True
        except Exception:
            return False

    def list_evidence(
        self,
        prefix: Optional[str] = None,
        limit: int = 100
    ) -> List[str]:
        """List evidence in Azure Blob."""
        list_prefix = f"{self.prefix}{prefix}" if prefix else self.prefix

        blobs = self.container_client.list_blobs(
            name_starts_with=list_prefix,
            results_per_page=limit
        )

        # Extract evidence IDs
        evidence_ids = []
        for blob in blobs:
            # Remove prefix and .json extension
            evidence_id = blob.name[len(self.prefix):].replace(".json", "")
            evidence_ids.append(evidence_id)

        return evidence_ids


class StorageRegistry:
    """
    Storage provider registry.

    Manages storage provider plugins.
    """

    def __init__(self):
        """Initialize storage registry."""
        self.providers: Dict[str, StorageProvider] = {}
        self._default_provider: Optional[str] = None

        # Register default local provider
        self.register("local", LocalStorageProvider())
        self.set_default("local")

    def register(self, name: str, provider: StorageProvider):
        """Register storage provider."""
        self.providers[name] = provider

    def unregister(self, name: str):
        """Unregister storage provider."""
        self.providers.pop(name, None)

    def get_provider(self, name: Optional[str] = None) -> Optional[StorageProvider]:
        """
        Get storage provider by name.

        Args:
            name: Provider name (uses default if None)

        Returns:
            StorageProvider or None
        """
        if name is None:
            name = self._default_provider

        return self.providers.get(name)

    def set_default(self, name: str):
        """Set default storage provider."""
        if name in self.providers:
            self._default_provider = name

    def list_providers(self) -> List[str]:
        """List registered provider names."""
        return list(self.providers.keys())


# Global storage registry
_global_registry: Optional[StorageRegistry] = None


def get_storage_registry() -> StorageRegistry:
    """Get or create global storage registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = StorageRegistry()
    return _global_registry


def get_default_storage() -> StorageProvider:
    """Get default storage provider."""
    registry = get_storage_registry()
    return registry.get_provider()
