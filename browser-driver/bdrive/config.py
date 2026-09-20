"""Deployment configuration for bdrive.

Every value here is a *deployment* fact — socket path, profile dir,
proxy URL — with a default matching ``browser-driver/SPEC.md`` §3 and
an environment override. Nothing in ``bdrive.protocol`` or
``bdrive.observation`` reads this module: the protocol must not cement
the same-box-proxy assumption (or any other deployment shape) behind
its interface (H17, GitHub #132).

Bad values fail loud at load time (:class:`ConfigError`), never as a
mysterious misbehaving daemon.
"""

import os


class ConfigError(ValueError):
    """A deployment value is missing or malformed."""


_MISSING = object()


def _env(name, default, env):
    """Fetch an override. A present-but-empty value is returned as-is
    so downstream validators fail loud — silently falling back to the
    default would deploy the daemon under different settings than the
    operator set (e.g. ``BDRIVE_USER=""`` deploying as ``bdrive``)."""
    if env is not None:
        value = env.get(name, _MISSING)
    else:
        value = os.environ.get(name, _MISSING)
    if value is _MISSING:
        return default
    return value


def _abs_path(name, value):
    if not isinstance(value, str) or not value.startswith("/"):
        raise ConfigError("%s must be an absolute path, got %r" % (name, value))
    return value


def _proxy_url(name, value):
    if not isinstance(value, str):
        raise ConfigError("%s must be a URL string, got %r" % (name, value))
    scheme = value.split(":", 1)[0].lower()
    if scheme not in ("http", "https"):
        raise ConfigError(
            "%s must be an http(s) URL, got %r" % (name, value)
        )
    return value


def _positive_int(name, value):
    if isinstance(value, bool):
        raise ConfigError("%s must be an int, got %r" % (name, value))
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ConfigError("%s must be an int, got %r" % (name, value))
    if number <= 0:
        raise ConfigError("%s must be positive, got %r" % (name, value))
    return number


class BDriveConfig:
    """Resolved deployment configuration. Read once at daemon start."""

    def __init__(self, env=None):
        get = lambda name, default: _env(name, default, env)
        self.socket_path = _abs_path(
            "BDRIVE_SOCKET", get("BDRIVE_SOCKET", "/run/bdrive/bdrive.sock")
        )
        self.profile_dir = _abs_path(
            "BDRIVE_PROFILE_DIR", get("BDRIVE_PROFILE_DIR", "/home/bdrive/profile")
        )
        # The egress proxy the browser's traffic is forced through.
        # Default is the same-box swapd; a deployment may point it at a
        # different proxy without touching the protocol (H17).
        self.proxy_url = _proxy_url(
            "BDRIVE_PROXY_URL",
            get("BDRIVE_PROXY_URL", "http://127.0.0.1:18080"),
        )
        self.job_base_dir = _abs_path(
            "BDRIVE_JOB_BASE_DIR",
            get("BDRIVE_JOB_BASE_DIR", "/home/bdrive/jobs"),
        )
        self.session_ttl_s = _positive_int(
            "BDRIVE_SESSION_TTL_S", get("BDRIVE_SESSION_TTL_S", "1800")
        )
        self.look_max_bytes = _positive_int(
            "BDRIVE_LOOK_MAX_BYTES", get("BDRIVE_LOOK_MAX_BYTES", "1500000")
        )
        self.service_user = get("BDRIVE_USER", "bdrive")
        if not self.service_user:
            raise ConfigError("BDRIVE_USER must be non-empty")
        self.client_group = get("BDRIVE_CLIENT_GROUP", "bdrive-clients")
        if not self.client_group:
            raise ConfigError("BDRIVE_CLIENT_GROUP must be non-empty")

    def as_dict(self):
        return {
            "socket_path": self.socket_path,
            "profile_dir": self.profile_dir,
            "proxy_url": self.proxy_url,
            "job_base_dir": self.job_base_dir,
            "session_ttl_s": self.session_ttl_s,
            "look_max_bytes": self.look_max_bytes,
            "service_user": self.service_user,
            "client_group": self.client_group,
        }


def load_config(env=None):
    """Load and validate the deployment configuration."""
    return BDriveConfig(env=env)
