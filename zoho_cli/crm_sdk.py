"""Optional Zoho CRM SDK adapter boundary.

The official SDK is intentionally optional. This module must stay importable
without `zohocrmsdk8_0` installed so the default HTTP CRM commands remain small
and predictable.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import contextlib
from dataclasses import asdict, dataclass, is_dataclass
from importlib import import_module
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from platformdirs import user_cache_dir

from zoho_cli import config as _config


SDK_ADAPTER_ID = "sdk-v8"
SDK_API_VERSION = "v8"
SDK_ENVIRONMENT_MODE = "production"
SDK_TOKEN_STORE_FILE = "tokens.csv"
SDK_RESOURCE_ENV_VAR = "ZOHO_CRM_SDK_RESOURCE_PATH"
CURRENT_HTTP_ADAPTER_ID = "http-v2"
SDK_IMPORT_ROOT = "zohocrmsdk"

READ_ONLY_METHODS = [
    "modules",
    "fields",
    "list_records",
    "get_record",
    "search_records",
]


@dataclass(frozen=True)
class CrmSdkEnvironmentSpec:
    """JSON-safe description of one SDK production data-center environment."""

    key: str
    legacy_region: str
    api_domain: str
    accounts_token_url: str
    file_upload_domain: str
    sdk_class_path: str
    sdk_class_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "legacyRegion": self.legacy_region,
            "apiDomain": self.api_domain,
            "accountsTokenUrl": self.accounts_token_url,
            "fileUploadDomain": self.file_upload_domain,
            "sdkClassPath": self.sdk_class_path,
            "sdkClassName": self.sdk_class_name,
            "environment": SDK_ENVIRONMENT_MODE,
        }


def _env(
    *,
    key: str,
    legacy_region: str,
    api_domain: str,
    accounts_token_url: str,
    file_upload_domain: str,
    module_name: str,
    class_name: str,
) -> CrmSdkEnvironmentSpec:
    return CrmSdkEnvironmentSpec(
        key=key,
        legacy_region=legacy_region,
        api_domain=api_domain,
        accounts_token_url=accounts_token_url,
        file_upload_domain=file_upload_domain,
        sdk_class_path=(
            f"zohocrmsdk.src.com.zoho.crm.api.dc.{module_name}.{class_name}"
        ),
        sdk_class_name=class_name,
    )


CRM_SDK_ENVIRONMENTS: dict[str, CrmSdkEnvironmentSpec] = {
    "us": _env(
        key="us",
        legacy_region="com",
        api_domain="https://www.zohoapis.com",
        accounts_token_url="https://accounts.zoho.com/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.com",
        module_name="us_data_center",
        class_name="USDataCenter",
    ),
    "eu": _env(
        key="eu",
        legacy_region="eu",
        api_domain="https://www.zohoapis.eu",
        accounts_token_url="https://accounts.zoho.eu/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.eu",
        module_name="eu_data_center",
        class_name="EUDataCenter",
    ),
    "in": _env(
        key="in",
        legacy_region="in",
        api_domain="https://www.zohoapis.in",
        accounts_token_url="https://accounts.zoho.in/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.in",
        module_name="in_data_center",
        class_name="INDataCenter",
    ),
    "au": _env(
        key="au",
        legacy_region="au",
        api_domain="https://www.zohoapis.com.au",
        accounts_token_url="https://accounts.zoho.com.au/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.com.au",
        module_name="au_data_center",
        class_name="AUDataCenter",
    ),
    "jp": _env(
        key="jp",
        legacy_region="jp",
        api_domain="https://www.zohoapis.jp",
        accounts_token_url="https://accounts.zoho.jp/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.jp",
        module_name="jp_data_center",
        class_name="JPDataCenter",
    ),
    "ca": _env(
        key="ca",
        legacy_region="ca",
        api_domain="https://www.zohoapis.ca",
        accounts_token_url="https://accounts.zohocloud.ca/oauth/v2/token",
        file_upload_domain="https://upload.zohocloud.ca",
        module_name="ca_data_center",
        class_name="CADataCenter",
    ),
    "cn": _env(
        key="cn",
        legacy_region="cn",
        api_domain="https://www.zohoapis.com.cn",
        accounts_token_url="https://accounts.zoho.com.cn/oauth/v2/token",
        file_upload_domain="https://content.zohoapis.com.cn",
        module_name="cn_data_center",
        class_name="CNDataCenter",
    ),
    "sa": _env(
        key="sa",
        legacy_region="sa",
        api_domain="https://www.zohoapis.sa",
        accounts_token_url="https://accounts.zoho.sa/oauth/v2/token",
        file_upload_domain="https://files.zoho.sa",
        module_name="sa_data_center",
        class_name="SADataCenter",
    ),
}

_HOST_TO_DATA_CENTER: dict[str, str] = {
    "accounts.zoho.com": "us",
    "mail.zoho.com": "us",
    "www.zohoapis.com": "us",
    "content.zohoapis.com": "us",
    "accounts.zoho.eu": "eu",
    "mail.zoho.eu": "eu",
    "www.zohoapis.eu": "eu",
    "content.zohoapis.eu": "eu",
    "accounts.zoho.in": "in",
    "mail.zoho.in": "in",
    "www.zohoapis.in": "in",
    "content.zohoapis.in": "in",
    "accounts.zoho.com.au": "au",
    "mail.zoho.com.au": "au",
    "www.zohoapis.com.au": "au",
    "content.zohoapis.com.au": "au",
    "accounts.zoho.jp": "jp",
    "mail.zoho.jp": "jp",
    "www.zohoapis.jp": "jp",
    "content.zohoapis.jp": "jp",
    "accounts.zohocloud.ca": "ca",
    "mail.zohocloud.ca": "ca",
    "www.zohocloud.ca": "ca",
    "www.zohoapis.ca": "ca",
    "upload.zohocloud.ca": "ca",
    "accounts.zoho.com.cn": "cn",
    "mail.zoho.com.cn": "cn",
    "www.zohoapis.com.cn": "cn",
    "content.zohoapis.com.cn": "cn",
    "accounts.zoho.sa": "sa",
    "mail.zoho.sa": "sa",
    "www.zohoapis.sa": "sa",
    "files.zoho.sa": "sa",
}


class CrmSdkUnavailableError(RuntimeError):
    """Raised when SDK-backed execution is requested but unavailable."""

    def __init__(self, code: str, details: str) -> None:
        self.code = code
        self.details = details
        super().__init__(f"{code}: {details}")

    def to_dict(self) -> dict[str, str]:
        return {"status": "error", "error": self.code, "details": self.details}


class CrmSdkAdapterNotInitialized(CrmSdkUnavailableError):
    """Raised when the adapter skeleton is used before a backend is attached."""


@dataclass(frozen=True)
class CrmSdkBindings:
    Initializer: object
    OAuthToken: object
    FileStore: object
    UserSignature: object
    SDKConfig: object
    ModulesOperations: object
    FieldsOperations: object
    RecordOperations: object
    DataCenter: object
    environment_spec: CrmSdkEnvironmentSpec


def _host_from_url(value: str | None) -> str:
    if not value:
        return ""
    parsed = urlparse(value)
    if parsed.netloc:
        return parsed.netloc.lower()
    parsed = urlparse(f"https://{value}")
    return parsed.netloc.lower()


def infer_crm_sdk_data_center(
    *,
    accounts_server: str | None = None,
    crm_base_url: str | None = None,
    mail_base_url: str | None = None,
) -> str:
    """Infer the SDK data-center key from existing CLI config values."""

    for value in (accounts_server, crm_base_url, mail_base_url):
        host = _host_from_url(value)
        if not host:
            continue
        if host in _HOST_TO_DATA_CENTER:
            return _HOST_TO_DATA_CENTER[host]
    return "us"


def crm_sdk_environment_spec(
    *,
    accounts_server: str | None = None,
    crm_base_url: str | None = None,
    mail_base_url: str | None = None,
) -> CrmSdkEnvironmentSpec:
    key = infer_crm_sdk_data_center(
        accounts_server=accounts_server,
        crm_base_url=crm_base_url,
        mail_base_url=mail_base_url,
    )
    return CRM_SDK_ENVIRONMENTS[key]


def crm_sdk_environment_spec_for_account(
    account_cfg: Mapping[str, Any] | None,
) -> CrmSdkEnvironmentSpec:
    account_cfg = account_cfg or {}
    return crm_sdk_environment_spec(
        accounts_server=_string_or_none(account_cfg.get("accounts_server")),
        crm_base_url=_string_or_none(
            account_cfg.get("crm_base_url") or account_cfg.get("crm_api_base_url")
        ),
        mail_base_url=_string_or_none(account_cfg.get("mail_base_url")),
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_account_slug(account_email: str | None) -> str:
    text = (account_email or "default").strip() or "default"
    text = text.replace("@", "_at_")
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in text)


def crm_sdk_resource_path(
    *,
    account_email: str | None = None,
    create: bool = False,
) -> Path:
    """Return the CLI-managed SDK resource directory for one account."""

    override = os.environ.get(SDK_RESOURCE_ENV_VAR)
    base = (
        Path(override).expanduser()
        if override
        else Path(user_cache_dir(_config.APP_NAME)) / "crm_sdk"
    )
    path = base / _safe_account_slug(account_email)
    if create:
        path.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            path.chmod(0o700)
    return path


def crm_sdk_token_store_path(resource_path: Path) -> Path:
    return resource_path / SDK_TOKEN_STORE_FILE


def build_crm_sdk_initialization_plan(
    *,
    account_cfg: Mapping[str, Any] | None = None,
    account_email: str | None = None,
    create_resource_path: bool = False,
) -> dict[str, Any]:
    """Build an AI-safe SDK initialization plan without importing the SDK."""

    spec = crm_sdk_environment_spec_for_account(account_cfg)
    resource_path = crm_sdk_resource_path(
        account_email=account_email,
        create=create_resource_path,
    )
    return {
        "adapter": SDK_ADAPTER_ID,
        "stage": "skeleton",
        "apiVersion": SDK_API_VERSION,
        "environment": SDK_ENVIRONMENT_MODE,
        "defaultEnabled": False,
        "currentCliAdapter": CURRENT_HTTP_ADAPTER_ID,
        "dataCenter": spec.to_dict(),
        "resourcePath": str(resource_path),
        "resourcePathEnvVar": SDK_RESOURCE_ENV_VAR,
        "resourcePathManagedByCli": True,
        "tokenStorePath": str(crm_sdk_token_store_path(resource_path)),
        "tokenStoreMode": "cli-managed-file-store-planned",
        "preventsSdkCwdDefaults": True,
        "readOnlyMethods": list(READ_ONLY_METHODS),
        "outputShape": {
            "plainJson": True,
            "unwrapDataForCli": True,
            "preserveCurrentCommands": True,
        },
        "next": [
            "Attach the official SDK backend behind an explicit adapter flag.",
            "Prove read-only parity before changing default CRM command behavior.",
        ],
    }


def crm_sdk_adapter_status(
    *,
    account_cfg: Mapping[str, Any] | None = None,
    account_email: str | None = None,
) -> dict[str, Any]:
    return build_crm_sdk_initialization_plan(
        account_cfg=account_cfg,
        account_email=account_email,
        create_resource_path=False,
    )


def _load_attr(path: str, importer: Callable[[str], Any]) -> object:
    module_path, attr = path.rsplit(".", 1)
    module = importer(module_path)
    return getattr(module, attr)


def load_crm_sdk_bindings(
    *,
    data_center_key: str = "us",
    importer: Callable[[str], Any] = import_module,
) -> CrmSdkBindings:
    """Lazy-load official SDK classes for future adapter execution."""

    spec = CRM_SDK_ENVIRONMENTS.get(data_center_key)
    if spec is None:
        raise CrmSdkUnavailableError(
            "unsupported_data_center",
            f"Unsupported CRM SDK data center: {data_center_key}",
        )

    paths = {
        "Initializer": "zohocrmsdk.src.com.zoho.crm.api.initializer.Initializer",
        "OAuthToken": "zohocrmsdk.src.com.zoho.api.authenticator.oauth_token.OAuthToken",
        "FileStore": "zohocrmsdk.src.com.zoho.api.authenticator.store.file_store.FileStore",
        "UserSignature": "zohocrmsdk.src.com.zoho.crm.api.user_signature.UserSignature",
        "SDKConfig": "zohocrmsdk.src.com.zoho.crm.api.sdk_config.SDKConfig",
        "ModulesOperations": (
            "zohocrmsdk.src.com.zoho.crm.api.modules."
            "modules_operations.ModulesOperations"
        ),
        "FieldsOperations": (
            "zohocrmsdk.src.com.zoho.crm.api.fields.fields_operations.FieldsOperations"
        ),
        "RecordOperations": (
            "zohocrmsdk.src.com.zoho.crm.api.record.record_operations.RecordOperations"
        ),
        "DataCenter": spec.sdk_class_path,
    }
    try:
        loaded = {name: _load_attr(path, importer) for name, path in paths.items()}
    except ModuleNotFoundError as exc:
        missing = exc.name or SDK_IMPORT_ROOT
        if missing == SDK_IMPORT_ROOT or missing.startswith(f"{SDK_IMPORT_ROOT}."):
            raise CrmSdkUnavailableError(
                "sdk_not_installed",
                "Install the optional dependency with: pip install 'zoho-cli[crm-sdk]'",
            ) from exc
        raise

    return CrmSdkBindings(
        Initializer=loaded["Initializer"],
        OAuthToken=loaded["OAuthToken"],
        FileStore=loaded["FileStore"],
        UserSignature=loaded["UserSignature"],
        SDKConfig=loaded["SDKConfig"],
        ModulesOperations=loaded["ModulesOperations"],
        FieldsOperations=loaded["FieldsOperations"],
        RecordOperations=loaded["RecordOperations"],
        DataCenter=loaded["DataCenter"],
        environment_spec=spec,
    )


def normalize_sdk_json(value: Any) -> Any:
    """Convert SDK models/responses into plain JSON-compatible values."""

    if value is None or isinstance(value, str | int | float | bool):
        return value
    if is_dataclass(value):
        return normalize_sdk_json(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): normalize_sdk_json(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [normalize_sdk_json(item) for item in value]

    get_object = getattr(value, "get_object", None)
    if callable(get_object):
        return normalize_sdk_json(get_object())

    get_data = getattr(value, "get_data", None)
    if callable(get_data):
        return {"data": normalize_sdk_json(get_data())}

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return normalize_sdk_json(to_dict())

    try:
        attrs = vars(value)
    except TypeError:
        return str(value)

    public = {
        key: val
        for key, val in attrs.items()
        if not key.startswith("_") and not callable(val)
    }
    if public:
        return normalize_sdk_json(public)

    return str(value)


class ZohoCrmSdkAdapter:
    """Read-only SDK adapter skeleton with injectable backend for parity tests."""

    def __init__(self, backend: object | None = None) -> None:
        self._backend = backend

    def _call(self, method: str, **kwargs: Any) -> dict | list:
        if self._backend is None:
            raise CrmSdkAdapterNotInitialized(
                "sdk_adapter_not_initialized",
                "CRM SDK adapter backend is not attached yet; use the default HTTP adapter.",
            )
        func = getattr(self._backend, method, None)
        if not callable(func):
            raise CrmSdkUnavailableError(
                "sdk_backend_method_missing",
                f"CRM SDK backend does not implement {method}",
            )
        payload = normalize_sdk_json(func(**kwargs))
        if not isinstance(payload, dict | list):
            payload = {"data": payload}
        return payload

    def modules(self, *, limit: int = 50, page: int = 1) -> dict | list:
        return self._call("modules", limit=limit, page=page)

    def fields(
        self, module_api_name: str, *, limit: int = 200, page: int = 1
    ) -> dict | list:
        return self._call(
            "fields",
            module_api_name=module_api_name,
            limit=limit,
            page=page,
        )

    def list_records(
        self,
        module_api_name: str,
        *,
        limit: int = 50,
        page: int = 1,
        fields: list[str] | None = None,
    ) -> dict | list:
        return self._call(
            "list_records",
            module_api_name=module_api_name,
            limit=limit,
            page=page,
            fields=list(fields or []),
        )

    def get_record(
        self,
        module_api_name: str,
        record_id: str,
        *,
        fields: list[str] | None = None,
    ) -> dict | list:
        return self._call(
            "get_record",
            module_api_name=module_api_name,
            record_id=record_id,
            fields=list(fields or []),
        )

    def search_records(
        self,
        module_api_name: str,
        *,
        criteria: str | None = None,
        word: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict | list:
        return self._call(
            "search_records",
            module_api_name=module_api_name,
            criteria=criteria,
            word=word,
            limit=limit,
            page=page,
        )
