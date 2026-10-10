"""
Configuration management for Custom Translations app.

Configuration sources (in priority order):
1. Environment variables (e.g., CUSTOM_TRANSLATIONS_API_KEY)
2. App-level config file: apps/custom_translations/config.json
   (user-created, not tracked in git, survives updates)
3. site_config.json "custom_translations_settings" key (legacy support)

Users only need to configure ONE source. Environment variables are recommended
for security (no key written to disk). For shared deployments, use config.json.

Required settings for auto-translation:
- API key (provider-specific)
- Provider: "deepseek", "nvidia", or any OpenAI-compatible endpoint
- API endpoint URL
- Model name

Example config.json:
{
    "provider": "nvidia",
    "api_key": "nvapi-xxx",
    "api_endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
    "model": "deepseek-ai/deepseek-v4-flash",
    "batch_size": 10,
    "max_length": 500
}

Example environment variables:
    CUSTOM_TRANSLATIONS_API_KEY=nvapi-xxx
    CUSTOM_TRANSLATIONS_PROVIDER=nvidia
    CUSTOM_TRANSLATIONS_ENDPOINT=https://integrate.api.nvidia.com/v1/chat/completions
    CUSTOM_TRANSLATIONS_MODEL=deepseek-ai/deepseek-v4-flash
"""

import json
import os
from pathlib import Path

# Default provider configurations (publicly known endpoints, no secrets)
DEFAULT_PROVIDERS = {
    "nvidia": {
        "api_endpoint": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "deepseek-ai/deepseek-v4-flash",
        "description": "NVIDIA NIM API (free tier available, requires nvapi-xxx key)",
    },
    "deepseek": {
        "api_endpoint": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "description": "DeepSeek official API (requires sk-xxx key, paid)",
    },
    "openai": {
        "api_endpoint": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "description": "OpenAI API (requires sk-xxx key, paid)",
    },
}

# Defaults for optional settings
DEFAULT_BATCH_SIZE = 10
DEFAULT_MAX_LENGTH = 500

#: How long the boot-time scan result is cached (seconds)
DEFAULT_SCAN_INTERVAL = 6 * 60 * 60

#: Config keys that must be coerced to int / bool
_INT_KEYS = ("batch_size", "max_length", "scan_interval_seconds")
_BOOL_KEYS = ("auto_translate", "scan_on_boot")


def get_app_root() -> Path:
    """Get the app root directory (where hooks.py lives)."""
    return Path(__file__).resolve().parent.parent


def get_config_file_path() -> Path:
    """Path to the user-editable config.json (in app root, not in git)."""
    return get_app_root() / "config.json"


def get_example_config_path() -> Path:
    """Path to the example config file (tracked in git for reference)."""
    return get_app_root() / "config.example.json"


def load_config() -> dict:
    """
    Load configuration from all sources with priority:
    1. Environment variables (highest priority)
    2. config.json (app-level, user-managed)
    3. site_config.json (legacy, lower priority)
    4. Defaults (lowest priority)

    Returns dict with keys:
        provider, api_key, api_endpoint, model, batch_size, max_length,
        auto_translate (bool), is_configured (bool, read-only)
    """
    config = {
        "provider": "nvidia",
        "api_key": "",
        "api_endpoint": "",
        "model": "",
        "batch_size": DEFAULT_BATCH_SIZE,
        "max_length": DEFAULT_MAX_LENGTH,
        "auto_translate": False,
        "scan_on_boot": True,
        "scan_interval_seconds": DEFAULT_SCAN_INTERVAL,
    }

    # Source 3: site_config.json (legacy support)
    try:
        import frappe
        site_cfg = frappe.conf.get("custom_translations_settings") or {}
        if site_cfg:
            _merge_config(config, site_cfg)
    except Exception:
        pass

    # Source 2: config.json (app-level, user-managed)
    config_path = get_config_file_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_cfg = json.load(f)
            _merge_config(config, file_cfg)
        except (json.JSONDecodeError, OSError) as e:
            pass

    # Source 1: environment variables (highest priority)
    env_mapping = {
        "CUSTOM_TRANSLATIONS_API_KEY": "api_key",
        "CUSTOM_TRANSLATIONS_PROVIDER": "provider",
        "CUSTOM_TRANSLATIONS_ENDPOINT": "api_endpoint",
        "CUSTOM_TRANSLATIONS_MODEL": "model",
        "CUSTOM_TRANSLATIONS_BATCH_SIZE": "batch_size",
        "CUSTOM_TRANSLATIONS_MAX_LENGTH": "max_length",
        "CUSTOM_TRANSLATIONS_AUTO_TRANSLATE": "auto_translate",
        "CUSTOM_TRANSLATIONS_SCAN_ON_BOOT": "scan_on_boot",
        "CUSTOM_TRANSLATIONS_SCAN_INTERVAL": "scan_interval_seconds",
    }
    for env_key, cfg_key in env_mapping.items():
        val = os.environ.get(env_key)
        if val is not None:
            if cfg_key in _INT_KEYS:
                try:
                    config[cfg_key] = int(val)
                except ValueError:
                    pass
            elif cfg_key in _BOOL_KEYS:
                config[cfg_key] = val.lower() in ("1", "true", "yes", "on")
            else:
                config[cfg_key] = val

    # Apply provider defaults if endpoint/model not set
    provider = config.get("provider", "nvidia").lower()
    if provider in DEFAULT_PROVIDERS:
        defaults = DEFAULT_PROVIDERS[provider]
        if not config.get("api_endpoint"):
            config["api_endpoint"] = defaults["api_endpoint"]
        if not config.get("model"):
            config["model"] = defaults["model"]

    # Normalize types
    try:
        config["batch_size"] = int(config.get("batch_size") or DEFAULT_BATCH_SIZE)
    except (TypeError, ValueError):
        config["batch_size"] = DEFAULT_BATCH_SIZE
    try:
        config["max_length"] = int(config.get("max_length") or DEFAULT_MAX_LENGTH)
    except (TypeError, ValueError):
        config["max_length"] = DEFAULT_MAX_LENGTH

    # Read-only flag: is auto-translation ready to use?
    config["is_configured"] = bool(
        config.get("api_key")
        and config.get("api_endpoint")
        and config.get("model")
    )
    config["auto_translate"] = bool(config.get("auto_translate"))
    config["scan_on_boot"] = bool(config.get("scan_on_boot", True))
    try:
        config["scan_interval_seconds"] = int(
            config.get("scan_interval_seconds") or DEFAULT_SCAN_INTERVAL
        )
    except (TypeError, ValueError):
        config["scan_interval_seconds"] = DEFAULT_SCAN_INTERVAL

    return config


def _merge_config(base: dict, overlay: dict):
    """Merge overlay dict into base dict (overlay takes priority)."""
    for key, value in overlay.items():
        if value is not None:
            base[key] = value


def is_configured() -> bool:
    """Quick check if auto-translation is configured."""
    return load_config().get("is_configured", False)


def get_setup_instructions() -> str:
    """Return human-readable setup instructions for first-time users."""
    return """
To enable automatic translation, configure your API key using ONE of these methods:

Method 1 - Environment variables (recommended for security):
    export CUSTOM_TRANSLATIONS_API_KEY="your-api-key-here"
    export CUSTOM_TRANSLATIONS_PROVIDER="nvidia"  # or deepseek, openai

Method 2 - Config file:
    Copy config.example.json to config.json in the app directory and fill in your API key.

Method 3 - site_config.json (legacy):
    Add to sites/{site}/site_config.json:
    "custom_translations_settings": {
        "provider": "nvidia",
        "api_key": "your-api-key-here"
    }

Supported providers:
    - nvidia: NVIDIA NIM API (free tier, model: deepseek-ai/deepseek-v4-flash)
    - deepseek: DeepSeek API (paid, model: deepseek-chat)
    - openai: OpenAI API (paid, model: gpt-4o-mini)

Get NVIDIA API key: https://build.nvidia.com/ (free credits available)
Get DeepSeek API key: https://platform.deepseek.com/
""".strip()
