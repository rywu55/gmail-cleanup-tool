from unittest.mock import MagicMock, patch, call

import pytest
from googleapiclient.errors import HttpError

from gmail_client import (
    GmailAPIError,
    BatchDeleteResult,
    batch_delete,
    list_message_ids,
    _parse_from,
    _parse_date,
)


def _http_error(status: int) -> HttpError:
    resp = MagicMock()
    resp.status = status
    return HttpError(resp=resp, content=b'error')


class TestListMessageIds:
    def test_returns_ids_newest_first(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': '1'}, {'id': '2'}, {'id': '3'}],
        }

        with patch('gmail_client._build_service', return_value=mock_service):
            ids = list_message_ids(mock_creds, max_results=3)

        assert ids == ['1', '2', '3']

    def test_paginates_until_max_results(self, mock_creds):
        mock_service = MagicMock()
        page1 = {'messages': [{'id': str(i)} for i in range(500)], 'nextPageToken': 'tok'}
        page2 = {'messages': [{'id': str(i)} for i in range(500, 1000)]}
        mock_service.users().messages().list().execute.side_effect = [page1, page2]

        with patch('gmail_client._build_service', return_value=mock_service):
            ids = list_message_ids(mock_creds, max_results=1000)

        assert len(ids) == 1000

    def test_stops_paginating_when_no_next_page_token(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            'messages': [{'id': '1'}],
        }

        with patch('gmail_client._build_service', return_value=mock_service):
            ids = list_message_ids(mock_creds, max_results=1000)

        assert ids == ['1']


class TestRetryLogic:
    def test_retries_on_429_and_succeeds(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.side_effect = [
            _http_error(429),
            {'messages': [{'id': 'abc'}]},
        ]

        with patch('gmail_client._build_service', return_value=mock_service), \
             patch('gmail_client.time.sleep'):
            ids = list_message_ids(mock_creds, max_results=1)

        assert ids == ['abc']

    def test_raises_gmail_api_error_after_max_retries(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.side_effect = _http_error(429)

        with patch('gmail_client._build_service', return_value=mock_service), \
             patch('gmail_client.time.sleep'):
            with pytest.raises(GmailAPIError):
                list_message_ids(mock_creds, max_results=1)

    def test_retries_on_5xx(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.side_effect = [
            _http_error(503),
            _http_error(503),
            {'messages': [{'id': 'ok'}]},
        ]

        with patch('gmail_client._build_service', return_value=mock_service), \
             patch('gmail_client.time.sleep'):
            ids = list_message_ids(mock_creds, max_results=1)

        assert ids == ['ok']

    def test_does_not_retry_on_4xx(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().list().execute.side_effect = _http_error(403)

        with patch('gmail_client._build_service', return_value=mock_service):
            with pytest.raises(GmailAPIError):
                list_message_ids(mock_creds, max_results=1)


class TestBatchDelete:
    def test_returns_all_deleted_on_success(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().batchDelete().execute.return_value = None

        with patch('gmail_client._build_service', return_value=mock_service):
            result = batch_delete(mock_creds, ['id1', 'id2', 'id3'])

        assert result.deleted == 3
        assert result.failed == []

    def test_returns_all_failed_on_api_error(self, mock_creds):
        mock_service = MagicMock()
        mock_service.users().messages().batchDelete().execute.side_effect = _http_error(500)

        with patch('gmail_client._build_service', return_value=mock_service), \
             patch('gmail_client.time.sleep'):
            result = batch_delete(mock_creds, ['id1', 'id2'])

        assert result.deleted == 0
        assert set(result.failed) == {'id1', 'id2'}

    def test_empty_ids_returns_zero(self, mock_creds):
        result = batch_delete(mock_creds, [])
        assert result.deleted == 0
        assert result.failed == []


class TestParseFrom:
    def test_parses_name_and_address(self):
        addr, name = _parse_from('John Doe <john@example.com>')
        assert addr == 'john@example.com'
        assert name == 'John Doe'

    def test_parses_bare_address(self):
        addr, name = _parse_from('john@example.com')
        assert 'john@example.com' in addr

    def test_handles_quoted_name(self):
        addr, name = _parse_from('"No Reply" <noreply@company.com>')
        assert addr == 'noreply@company.com'


class TestParseDate:
    def test_uses_internal_date_ms(self):
        ts = _parse_date('', '1700000000000')
        assert ts == 1700000000

    def test_falls_back_to_zero_on_empty(self):
        ts = _parse_date('', None)
        assert ts == 0
