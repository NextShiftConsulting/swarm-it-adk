"""
Configuration Manager for Swarm-It

P17 Principle: ALL credential access MUST flow through config_manager.

Priority (3-Tier):
1. Environment variables (highest)
2. Config file (swarm_it_config.yaml)
3. Defaults (lowest)

Usage:
    from config.config_manager import get_config

    config = get_config()
    api_key = config.openai_api_key
    threshold = config.kappa_threshold
"""

import os
from pathlib import Path
from typing import Any, Optional, Dict

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigManager:
    """
    Centralized configuration management.

    Single gateway for all credentials and configuration.
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        "kappa_threshold": 0.7,
        "N_threshold": 0.5,
        "sigma_threshold": 0.7,
        "R_min": 0.3,
        "S_min": 0.4,
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize config manager.

        Args:
            config_file: Path to config YAML (optional)
        """
        if config_file is None:
            # Look in standard locations
            candidates = [
                Path.cwd() / "swarm_it_config.yaml",
                Path.cwd() / "config" / "swarm_it_config.yaml",
                Path.home() / ".swarm_it" / "config.yaml",
            ]
            for candidate in candidates:
                if candidate.exists():
                    config_file = str(candidate)
                    break

        self.config_file = Path(config_file) if config_file else None
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not YAML_AVAILABLE:
            return {}

        if self.config_file is None or not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Supports dot notation: 'llm.api_key'
        Environment variables override config file.

        Args:
            key: Configuration key
            default: Default value if not found

        Returns:
            Configuration value
        """
        # Check environment variable first
        env_key = f"SWARM_IT_{key.upper().replace('.', '_')}"
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # Navigate nested dict
        value = self._config
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default

            if value is None:
                return default

        return value

    # === Environment ===

    @property
    def environment(self) -> str:
        """Get current environment (dev, staging, prod)."""
        return os.getenv('SWARM_IT_ENVIRONMENT') or os.getenv('ENVIRONMENT') or self.get('environment', 'dev')

    @property
    def debug(self) -> bool:
        """Debug mode enabled."""
        val = os.getenv('SWARM_IT_DEBUG') or self.get('debug', 'false')
        return str(val).lower() in ('true', '1', 'yes')

    # === Server ===

    @property
    def host(self) -> str:
        """Server host."""
        return os.getenv('SWARM_IT_HOST') or self.get('server.host', '0.0.0.0')

    @property
    def port(self) -> int:
        """Server port."""
        val = os.getenv('SWARM_IT_PORT') or os.getenv('PORT') or self.get('server.port', 8080)
        return int(val)

    @property
    def grpc_port(self) -> int:
        """gRPC server port."""
        val = os.getenv('SWARM_IT_GRPC_PORT') or self.get('server.grpc_port', 9090)
        return int(val)

    # === Database ===

    @property
    def db_path(self) -> Optional[str]:
        """Database path (SQLite). None for in-memory."""
        return os.getenv('SWARM_IT_DB_PATH') or self.get('database.path')

    @property
    def db_url(self) -> Optional[str]:
        """Database URL (Postgres). Takes precedence over db_path."""
        return os.getenv('SWARM_IT_DB_URL') or os.getenv('DATABASE_URL') or self.get('database.url')

    # === Thresholds ===

    @property
    def kappa_threshold(self) -> float:
        """Kappa gate threshold."""
        val = os.getenv('SWARM_IT_KAPPA_THRESHOLD') or self.get('thresholds.kappa', self.DEFAULT_THRESHOLDS['kappa_threshold'])
        return float(val)

    @property
    def N_threshold(self) -> float:
        """Noise rejection threshold."""
        val = os.getenv('SWARM_IT_N_THRESHOLD') or self.get('thresholds.N', self.DEFAULT_THRESHOLDS['N_threshold'])
        return float(val)

    @property
    def sigma_threshold(self) -> float:
        """Stability threshold."""
        val = os.getenv('SWARM_IT_SIGMA_THRESHOLD') or self.get('thresholds.sigma', self.DEFAULT_THRESHOLDS['sigma_threshold'])
        return float(val)

    def get_thresholds(self) -> Dict[str, float]:
        """Get all threshold values."""
        return {
            'kappa_threshold': self.kappa_threshold,
            'N_threshold': self.N_threshold,
            'sigma_threshold': self.sigma_threshold,
            'R_min': float(os.getenv('SWARM_IT_R_MIN') or self.get('thresholds.R_min', self.DEFAULT_THRESHOLDS['R_min'])),
            'S_min': float(os.getenv('SWARM_IT_S_MIN') or self.get('thresholds.S_min', self.DEFAULT_THRESHOLDS['S_min'])),
        }

    # === LLM Credentials (for real RSCT computation) ===

    @property
    def openai_api_key(self) -> Optional[str]:
        """
        OpenAI API key.

        Priority:
        1. SWARM_IT_OPENAI_API_KEY
        2. OPENAI_API_KEY
        3. Config file llm.openai_api_key
        """
        return (
            os.getenv('SWARM_IT_OPENAI_API_KEY') or
            os.getenv('OPENAI_API_KEY') or
            self.get('llm.openai_api_key')
        )

    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Anthropic API key."""
        return (
            os.getenv('SWARM_IT_ANTHROPIC_API_KEY') or
            os.getenv('ANTHROPIC_API_KEY') or
            self.get('llm.anthropic_api_key')
        )

    @property
    def llm_provider(self) -> str:
        """LLM provider (openai, anthropic, bedrock)."""
        return os.getenv('SWARM_IT_LLM_PROVIDER') or self.get('llm.provider', 'openai')

    @property
    def llm_model(self) -> str:
        """LLM model for embeddings/analysis."""
        return os.getenv('SWARM_IT_LLM_MODEL') or self.get('llm.model', 'text-embedding-3-small')

    # === AWS (for production deployment) ===

    @property
    def aws_region(self) -> str:
        """AWS region."""
        return os.getenv('AWS_REGION') or self.get('aws.region', 'us-east-1')

    @property
    def aws_access_key_id(self) -> Optional[str]:
        """AWS access key (prefer IAM roles in production)."""
        return os.getenv('AWS_ACCESS_KEY_ID') or self.get('aws.access_key_id')

    @property
    def aws_secret_access_key(self) -> Optional[str]:
        """AWS secret key (prefer IAM roles in production)."""
        return os.getenv('AWS_SECRET_ACCESS_KEY') or self.get('aws.secret_access_key')

    # === Authentication ===

    @property
    def api_key_required(self) -> bool:
        """Whether API key authentication is required."""
        val = os.getenv('SWARM_IT_API_KEY_REQUIRED') or self.get('auth.api_key_required', 'false')
        return str(val).lower() in ('true', '1', 'yes')

    @property
    def api_keys(self) -> list:
        """List of valid API keys."""
        keys = os.getenv('SWARM_IT_API_KEYS')
        if keys:
            return [k.strip() for k in keys.split(',')]
        return self.get('auth.api_keys', [])


# Global config instance (singleton)
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config


def reset_config() -> None:
    """Reset config (for testing)."""
    global _config
    _config = None
