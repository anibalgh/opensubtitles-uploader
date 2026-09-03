"""Tests for the minimal XML-RPC client (wire format + response parsing)."""

from __future__ import annotations

from opensubtitles_uploader.adapters.osapi.xmlrpc import (
    XmlRpcError,
    method_call,
    parse_response,
)


def test_method_call_encoding():
    body = method_call("LogIn", ["alice", "secret", "en", "app"])
    text = body.decode("utf-8")
    assert text.startswith("<?xml")
    assert "<methodName>LogIn</methodName>" in text
    assert "<string>alice</string>" in text
    assert "secret" in text


def test_parse_simple_response():
    xml = b"""<?xml version="1.0"?>
    <methodResponse><params><param><value><string>hello</string></value></param></params></methodResponse>"""
    assert parse_response(xml) == "hello"


def test_parse_struct_response():
    xml = b"""<?xml version="1.0"?>
    <methodResponse><params><param><value><struct>
      <member><name>token</name><value><string>abc123</string></value></member>
      <member><name>status</name><value><string>200 OK</string></value></member>
      <member><name>alreadyindb</name><value><int>0</int></value></member>
      <member><name>seconds</name><value><double>0.5</double></value></member>
    </struct></value></param></params></methodResponse>"""
    result = parse_response(xml)
    assert result == {"token": "abc123", "status": "200 OK", "alreadyindb": 0, "seconds": 0.5}


def test_parse_array_of_structs():
    xml = b"""<?xml version="1.0"?>
    <methodResponse><params><param><value><array><data>
      <value><struct><member><name>SubLanguageID</name><value><string>eng</string></value></member></struct></value>
      <value><struct><member><name>SubLanguageID</name><value><string>spa</string></value></member></struct></value>
    </data></array></value></param></params></methodResponse>"""
    assert parse_response(xml) == [{"SubLanguageID": "eng"}, {"SubLanguageID": "spa"}]


def test_parse_fault_raises():
    xml = b"""<?xml version="1.0"?>
    <methodResponse><fault><value><struct>
      <member><name>faultCode</name><value><int>401</int></value></member>
      <member><name>faultString</name><value><string>Unauthorized</string></value></member>
    </struct></value></fault></methodResponse>"""
    try:
        parse_response(xml)
    except XmlRpcError as exc:
        assert "Unauthorized" in exc.message
    else:  # pragma: no cover
        raise AssertionError("expected XmlRpcError")


def test_parse_rejects_doctype():
    xml = b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><methodResponse/>'
    try:
        parse_response(xml)
    except XmlRpcError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected XmlRpcError for unsafe payload")
