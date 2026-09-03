"""Minimal, dependency-free XML-RPC client.

The OpenSubtitles upload flow (``LogIn``, ``TryUploadSubtitles``,
``UploadSubtitles``) still runs over the legacy XML-RPC endpoint at
``https://api.opensubtitles.org/xml-rpc`` — the public REST API exposes
no upload endpoint (verified 2026-09-03).

Implemented from scratch on top of httpx for full control over timeouts
and TLS, with a strict payload parser (DOCTYPE/ENTITY rejected).
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import xml.etree.ElementTree as ET  # nosec B405
from typing import Any

import httpx

from opensubtitles_uploader.domain.errors import ApiError, AuthError, UploadFailedError


class XmlRpcError(ApiError):
    """Transport-level XML-RPC failure (network or fault)."""

    def __init__(self, message: str, code: str = "xmlrpc_error") -> None:
        super().__init__(code=code, message=message)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------


def _value_element(tag: str, value: Any) -> ET.Element:
    elem = ET.Element("param") if tag == "param" else ET.Element("member")
    return elem


def _value_xml(value: Any) -> ET.Element:
    """Wrap a Python value into a ``<value>`` element."""
    elem = ET.Element("value")
    child: ET.Element
    if value is None:
        child = ET.SubElement(elem, "nil")
    elif isinstance(value, bool):
        child = ET.SubElement(elem, "boolean")
        child.text = "1" if value else "0"
    elif isinstance(value, int):
        child = ET.SubElement(elem, "int")
        child.text = str(value)
    elif isinstance(value, float):
        child = ET.SubElement(elem, "double")
        child.text = repr(value)
    elif isinstance(value, bytes):
        child = ET.SubElement(elem, "base64")
        child.text = base64.b64encode(value).decode("ascii")
    elif isinstance(value, str):
        child = ET.SubElement(elem, "string")
        child.text = value
    elif isinstance(value, dict):
        child = ET.SubElement(elem, "struct")
        for key, item in value.items():
            member = ET.SubElement(child, "member")
            name = ET.SubElement(member, "name")
            name.text = str(key)
            member.append(_value_xml(item))
    elif isinstance(value, (list, tuple)):
        child = ET.SubElement(elem, "array")
        data = ET.SubElement(child, "data")
        for item in value:
            data.append(_value_xml(item))
    else:  # pragma: no cover - defensive
        raise TypeError(f"Unsupported XML-RPC value: {type(value)!r}")
    return elem


def method_call(method: str, params: list[Any]) -> bytes:
    root = ET.Element("methodCall")
    name = ET.SubElement(root, "methodName")
    name.text = method
    p = ET.SubElement(root, "params")
    for value in params:
        p.append(_value_xml(value))
    body: bytes = ET.tostring(root, encoding="utf-8")
    return b'<?xml version="1.0"?>\n' + body


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------


def _parse_value(node: ET.Element) -> Any:
    if node.tag != "value":
        nested = node.find("value")
        if nested is not None:
            node = nested
    for child in node:
        tag = child.tag
        text = (child.text or "").strip()
        if tag in {"int", "i4", "i8"}:
            return int(text)
        if tag == "boolean":
            return text == "1"
        if tag == "double":
            return float(text)
        if tag == "string":
            return child.text or ""
        if tag in {"nil"}:
            return None
        if tag == "base64":
            try:
                return base64.b64decode(text)
            except (binascii.Error, ValueError):
                return text
        if tag == "dateTime.iso8601":
            return text
        if tag == "array":
            data = child.find("data")
            if data is None:
                return []
            return [_parse_value(v) for v in data.findall("value")]
        if tag == "struct":
            result: dict[str, Any] = {}
            for member in child.findall("member"):
                name = member.findtext("name") or ""
                value = member.find("value")
                result[name] = _parse_value(value) if value is not None else None
            return result
        if tag == "value":  # nested <value>
            return _parse_value(child)
    return node.text if node.text is not None else None


def parse_response(body: bytes) -> Any:
    """Parse an XML-RPC ``methodResponse``; raise on transport faults."""
    if not body or b"<!DOCTYPE" in body or b"<!ENTITY" in body:
        raise XmlRpcError("Unsafe XML-RPC payload received.")
    try:
        root = ET.fromstring(body)  # nosec B314
    except ET.ParseError as exc:
        raise XmlRpcError(f"Malformed XML-RPC response: {exc}") from exc

    if root.tag != "methodResponse":
        raise XmlRpcError("Not an XML-RPC methodResponse.")

    fault = root.find("fault")
    if fault is not None:
        detail = _parse_value(fault)
        message = str(
            (detail or {}).get("faultString") or (detail or {}).get("faultCode") or "XML-RPC fault"
        )
        raise XmlRpcError(message, code="xmlrpc_fault")

    params = root.find("params")
    if params is None:
        return None
    values = params.findall("param/value")
    if not values:
        return None
    return _parse_value(values[0]) if len(values) == 1 else [_parse_value(v) for v in values]


# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------


class XmlRpcClient:
    """Small typed wrapper around the legacy XML-RPC endpoint."""

    def __init__(
        self,
        base_url: str = "https://api.opensubtitles.org/xml-rpc",
        user_agent: str = "OpenSubtitles-Uploader",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._http = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": self._user_agent},
        )

    # -- transport ---------------------------------------------------------
    def call(self, method: str, params: list[Any]) -> Any:
        body = method_call(method, params)
        try:
            response = self._http.post(
                self._base_url,
                content=body,
                headers={"Content-Type": "text/xml"},
            )
        except httpx.HTTPError as exc:
            raise XmlRpcError(str(exc), code="network_error") from exc

        if response.status_code != 200:
            raise XmlRpcError(
                f"XML-RPC returned HTTP {response.status_code}.",
                code="service_unavailable",
            )
        return parse_response(response.content)

    # -- domain operations ---------------------------------------------------
    def login(self, username: str, password: str, language: str = "en") -> str:
        try:
            result = self.call("LogIn", [username, password, language, self._user_agent])
        except XmlRpcError as exc:
            message = str(exc)
            lowered = message.lower()
            if any(
                word in lowered
                for word in ("401", "unauthorized", "incorrect", "wrong", "password")
            ):
                message = "Wrong username or password"
            raise AuthError(message) from exc
        result = result or {}
        # The server reports success/failure through ``status``; a token may
        # be present even on failure, so it is *not* the success signal.
        status = str(result.get("status") or "")
        if not status.startswith("200"):
            message = status if status else "OpenSubtitles rejected the login."
            if any(word in message.lower() for word in ("401", "unauthorized")):
                message = "Wrong username or password"
            raise AuthError(message, code="auth_error")
        token = result.get("token")
        if not token:
            raise AuthError("OpenSubtitles rejected the login.", code="auth_error")
        return str(token)

    def logout(self, token: str) -> None:
        with contextlib.suppress(XmlRpcError):
            self.call("LogOut", [token])

    def get_sub_languages(self) -> list[dict[str, str]]:
        """Return ``[{SubLanguageID, LanguageName, ISO639}]`` (anonymous OK)."""
        try:
            result = self.call("GetSubLanguages", [])
        except XmlRpcError:
            return []
        data = result.get("data") if isinstance(result, dict) else None
        return [dict(item) for item in data] if isinstance(data, list) else []

    def try_upload_subtitles(
        self,
        token: str,
        cd1: dict[str, Any],
    ) -> dict[str, Any]:
        """Ask whether the subtitle already exists (and match the movie)."""
        try:
            result = self.call("TryUploadSubtitles", [token, {"cd1": cd1}])
        except XmlRpcError as exc:
            raise UploadFailedError(exc.message) from exc
        return result if isinstance(result, dict) else {}

    def upload_subtitles(
        self,
        token: str,
        baseinfo: dict[str, Any],
        cd1: dict[str, Any],
    ) -> dict[str, Any]:
        """Upload a subtitle.  Returns ``{status, data, seconds}``."""
        try:
            result = self.call("UploadSubtitles", [token, {"baseinfo": baseinfo, "cd1": cd1}])
        except XmlRpcError as exc:
            raise UploadFailedError(exc.message) from exc
        return result if isinstance(result, dict) else {}
