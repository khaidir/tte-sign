"""Tests for ID generators."""

from __future__ import annotations

import re

from app.core.ids import new_asset_id, new_document_id, new_request_id

_PATTERN = re.compile(r"^(doc|ast|req)_[0-9A-Z]{26}$")


class TestIds:
    def test_document_id_format(self):
        id_ = new_document_id()
        assert _PATTERN.match(id_), f"Invalid doc ID: {id_}"
        assert id_.startswith("doc_")

    def test_asset_id_format(self):
        id_ = new_asset_id()
        assert _PATTERN.match(id_), f"Invalid ast ID: {id_}"
        assert id_.startswith("ast_")

    def test_request_id_format(self):
        id_ = new_request_id()
        assert _PATTERN.match(id_), f"Invalid req ID: {id_}"
        assert id_.startswith("req_")

    def test_ids_are_unique(self):
        ids = {new_document_id() for _ in range(100)}
        assert len(ids) == 100
