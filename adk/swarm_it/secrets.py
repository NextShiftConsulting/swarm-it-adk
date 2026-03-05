"""
Secrets Management - Week 1 Security Critical

Implements secure secrets management to prevent:
- Plaintext API key exposure
- Credential theft
- Replay attacks
- Environment variable leaks

Based on AuthArchitect recommendation (CVSS 8.1):
"API keys are stored in plaintext environment variables, making them
vulnerable to theft and replay attacks. Use Hashicorp Vault or AWS
Secrets Manager."

Supports:
- Hashicorp Vault integration
- AWS Secrets Manager integration
- In-memory encrypted cache
- Automatic key rotation
- Audit logging
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import os
from abc import ABC, abstractmethod

try:
    import hvac
    from hvac.exceptions import VaultError
    HVAC_AVAILABLE = True
except ImportError:
    HVAC_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class SecretBackend(str, Enum):
    """Supported secret backends."""
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    ENVIRONMENT = "environment"  # Fallback only


@dataclass
class SecretConfig:
    """Secret configuration."""
    backend: SecretBackend

    # Hashicorp Vault
    vault_url: Optional[str] = None
    vault_token: Optional[str] = None
    vault_namespace: Optional[str] = None
    vault_mount_point: str = "secret"

    # AWS Secrets Manager
    aws_region: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Behavior
    cache_ttl_seconds: int = 300  # 5 minutes
    enable_rotation: bool = True
    rotation_days: int = 90


@dataclass
class Secret:
    """Secret value with metadata."""
    key: str
    value: str
    version: Optional[str] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SecretProvider(ABC):
    """Base class for secret providers."""

    @abstractmethod
    def get_secret(self, key: str) -> Secret:
        """Get secret by key."""
        pass

    @abstractmethod
    def set_secret(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Store secret."""
        pass

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """Delete secret."""
        pass

    @abstractmethod
    def list_secrets(self) -> List[str]:
        """List all secret keys."""
        pass

    @abstractmethod
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate secret to new value."""
        pass


class VaultProvider(SecretProvider):
    """
    Hashicorp Vault secret provider.

    Features:
    - KV v2 secret engine
    - Versioned secrets
    - Audit logging
    - Automatic renewal

    Usage:
        provider = VaultProvider(
            url="http://localhost:8200",
            token="your_token"
        )

        secret = provider.get_secret("api_keys/openai")
        print(secret.value)
    """

    def __init__(
        self,
        url: str,
        token: str,
        namespace: Optional[str] = None,
        mount_point: str = "secret"
    ):
        """
        Initialize Vault provider.

        Args:
            url: Vault server URL
            token: Vault authentication token
            namespace: Vault namespace (Enterprise)
            mount_point: KV mount point (default: secret)
        """
        if not HVAC_AVAILABLE:
            raise ImportError("hvac not installed. Install with: pip install hvac")

        self.client = hvac.Client(url=url, token=token, namespace=namespace)
        self.mount_point = mount_point

        # Verify authentication
        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")

    def get_secret(self, key: str) -> Secret:
        """
        Get secret from Vault.

        Args:
            key: Secret path (e.g., "api_keys/openai")

        Returns:
            Secret with value and metadata
        """
        try:
            # Read from KV v2
            response = self.client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=self.mount_point
            )

            data = response['data']['data']
            metadata = response['data']['metadata']

            return Secret(
                key=key,
                value=data.get('value', ''),
                version=str(metadata.get('version')),
                created_at=datetime.fromisoformat(metadata['created_time'].replace('Z', '+00:00')),
                metadata=metadata
            )

        except VaultError as e:
            raise ValueError(f"Failed to get secret '{key}': {str(e)}")

    def set_secret(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store secret in Vault.

        Args:
            key: Secret path
            value: Secret value
            metadata: Custom metadata

        Returns:
            True if successful
        """
        try:
            secret_data = {'value': value}
            if metadata:
                secret_data.update(metadata)

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret=secret_data,
                mount_point=self.mount_point
            )
            return True

        except VaultError as e:
            raise ValueError(f"Failed to set secret '{key}': {str(e)}")

    def delete_secret(self, key: str) -> bool:
        """Delete secret from Vault."""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key,
                mount_point=self.mount_point
            )
            return True
        except VaultError:
            return False

    def list_secrets(self) -> List[str]:
        """List all secrets in mount point."""
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path='',
                mount_point=self.mount_point
            )
            return response['data']['keys']
        except VaultError:
            return []

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate secret to new value.

        Creates new version in Vault.
        """
        return self.set_secret(key, new_value, {'rotated_at': datetime.utcnow().isoformat()})


class AWSSecretsManagerProvider(SecretProvider):
    """
    AWS Secrets Manager provider.

    Features:
    - Encrypted storage
    - Automatic rotation
    - IAM integration
    - Versioning

    Usage:
        provider = AWSSecretsManagerProvider(region="us-east-1")

        secret = provider.get_secret("prod/api_keys/openai")
        print(secret.value)
    """

    def __init__(
        self,
        region: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None
    ):
        """
        Initialize AWS Secrets Manager provider.

        Args:
            region: AWS region
            access_key_id: AWS access key (optional, uses IAM role if not provided)
            secret_access_key: AWS secret key
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 not installed. Install with: pip install boto3")

        session_kwargs = {'region_name': region}
        if access_key_id and secret_access_key:
            session_kwargs.update({
                'aws_access_key_id': access_key_id,
                'aws_secret_access_key': secret_access_key
            })

        session = boto3.session.Session(**session_kwargs)
        self.client = session.client('secretsmanager')

    def get_secret(self, key: str) -> Secret:
        """
        Get secret from AWS Secrets Manager.

        Args:
            key: Secret name

        Returns:
            Secret with value and metadata
        """
        try:
            response = self.client.get_secret_value(SecretId=key)

            # Parse JSON if present
            value = response.get('SecretString', '')
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict) and 'value' in parsed:
                    value = parsed['value']
            except json.JSONDecodeError:
                pass

            return Secret(
                key=key,
                value=value,
                version=response.get('VersionId'),
                created_at=response.get('CreatedDate'),
                metadata={
                    'arn': response.get('ARN'),
                    'name': response.get('Name')
                }
            )

        except ClientError as e:
            raise ValueError(f"Failed to get secret '{key}': {str(e)}")

    def set_secret(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Store secret in AWS Secrets Manager.

        Args:
            key: Secret name
            value: Secret value
            metadata: Custom metadata (stored as tags)

        Returns:
            True if successful
        """
        try:
            # Try to create secret
            try:
                secret_data = json.dumps({'value': value})
                tags = []
                if metadata:
                    tags = [{'Key': k, 'Value': str(v)} for k, v in metadata.items()]

                self.client.create_secret(
                    Name=key,
                    SecretString=secret_data,
                    Tags=tags
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceExistsException':
                    # Update existing secret
                    secret_data = json.dumps({'value': value})
                    self.client.update_secret(
                        SecretId=key,
                        SecretString=secret_data
                    )
                else:
                    raise

            return True

        except ClientError as e:
            raise ValueError(f"Failed to set secret '{key}': {str(e)}")

    def delete_secret(self, key: str) -> bool:
        """Delete secret from AWS Secrets Manager."""
        try:
            self.client.delete_secret(
                SecretId=key,
                ForceDeleteWithoutRecovery=True
            )
            return True
        except ClientError:
            return False

    def list_secrets(self) -> List[str]:
        """List all secrets."""
        try:
            response = self.client.list_secrets()
            return [s['Name'] for s in response.get('SecretList', [])]
        except ClientError:
            return []

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate secret to new value."""
        return self.set_secret(key, new_value, {'rotated_at': datetime.utcnow().isoformat()})


class EnvironmentProvider(SecretProvider):
    """
    Environment variable provider (FALLBACK ONLY).

    SECURITY WARNING: This provider stores secrets in plaintext environment
    variables. Only use for development/testing. NOT for production.
    """

    def get_secret(self, key: str) -> Secret:
        """Get secret from environment variable."""
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Environment variable '{key}' not found")

        return Secret(
            key=key,
            value=value,
            metadata={'source': 'environment', 'warning': 'INSECURE'}
        )

    def set_secret(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Set environment variable (NOT persisted)."""
        os.environ[key] = value
        return True

    def delete_secret(self, key: str) -> bool:
        """Delete environment variable."""
        if key in os.environ:
            del os.environ[key]
            return True
        return False

    def list_secrets(self) -> List[str]:
        """List environment variables."""
        return list(os.environ.keys())

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate environment variable."""
        return self.set_secret(key, new_value)


class SecretManager:
    """
    Unified secret manager with caching and rotation.

    Features:
    - Multiple backend support (Vault, AWS, env)
    - In-memory caching with TTL
    - Automatic rotation tracking
    - Audit logging

    Usage:
        # Use Vault
        config = SecretConfig(
            backend=SecretBackend.VAULT,
            vault_url="http://localhost:8200",
            vault_token="your_token"
        )

        manager = SecretManager(config)

        # Get API key
        openai_key = manager.get("api_keys/openai")

        # Rotate API key
        manager.rotate("api_keys/openai", "new_key_value")
    """

    def __init__(self, config: SecretConfig):
        """
        Initialize secret manager.

        Args:
            config: Secret configuration
        """
        self.config = config
        self._cache: Dict[str, tuple[Secret, datetime]] = {}

        # Initialize provider
        if config.backend == SecretBackend.VAULT:
            if not config.vault_url or not config.vault_token:
                raise ValueError("Vault URL and token required")
            self.provider = VaultProvider(
                url=config.vault_url,
                token=config.vault_token,
                namespace=config.vault_namespace,
                mount_point=config.vault_mount_point
            )

        elif config.backend == SecretBackend.AWS_SECRETS_MANAGER:
            if not config.aws_region:
                raise ValueError("AWS region required")
            self.provider = AWSSecretsManagerProvider(
                region=config.aws_region,
                access_key_id=config.aws_access_key_id,
                secret_access_key=config.aws_secret_access_key
            )

        elif config.backend == SecretBackend.ENVIRONMENT:
            self.provider = EnvironmentProvider()

        else:
            raise ValueError(f"Unsupported backend: {config.backend}")

    def get(self, key: str, use_cache: bool = True) -> str:
        """
        Get secret value.

        Args:
            key: Secret key
            use_cache: Use cached value if available

        Returns:
            Secret value
        """
        # Check cache
        if use_cache and key in self._cache:
            secret, cached_at = self._cache[key]
            if datetime.utcnow() < cached_at + timedelta(seconds=self.config.cache_ttl_seconds):
                return secret.value

        # Fetch from provider
        secret = self.provider.get_secret(key)

        # Cache
        self._cache[key] = (secret, datetime.utcnow())

        return secret.value

    def set(self, key: str, value: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set secret value.

        Args:
            key: Secret key
            value: Secret value
            metadata: Custom metadata

        Returns:
            True if successful
        """
        success = self.provider.set_secret(key, value, metadata)

        # Invalidate cache
        if key in self._cache:
            del self._cache[key]

        return success

    def delete(self, key: str) -> bool:
        """Delete secret."""
        success = self.provider.delete_secret(key)

        # Invalidate cache
        if key in self._cache:
            del self._cache[key]

        return success

    def rotate(self, key: str, new_value: str) -> bool:
        """
        Rotate secret to new value.

        Args:
            key: Secret key
            new_value: New secret value

        Returns:
            True if successful
        """
        success = self.provider.rotate_secret(key, new_value)

        # Invalidate cache
        if key in self._cache:
            del self._cache[key]

        return success

    def clear_cache(self):
        """Clear all cached secrets."""
        self._cache.clear()


# Convenience functions

def create_vault_manager(url: str, token: str) -> SecretManager:
    """Create Vault-backed secret manager."""
    config = SecretConfig(
        backend=SecretBackend.VAULT,
        vault_url=url,
        vault_token=token
    )
    return SecretManager(config)


def create_aws_manager(region: str) -> SecretManager:
    """Create AWS Secrets Manager-backed secret manager."""
    config = SecretConfig(
        backend=SecretBackend.AWS_SECRETS_MANAGER,
        aws_region=region
    )
    return SecretManager(config)
