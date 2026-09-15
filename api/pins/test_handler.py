"""Basic tests for the pins Lambda handler."""
import json
import unittest
from unittest.mock import MagicMock, patch


def _make_event(method, body=None, path_params=None, user_sub='user-123'):
    event = {
        'httpMethod': method,
        'requestContext': {
            'authorizer': {
                'claims': {'sub': user_sub}
            }
        },
        'pathParameters': path_params or {},
        'body': json.dumps(body) if body else None,
    }
    return event


class TestPinHandler(unittest.TestCase):

    def setUp(self):
        self.mock_table = MagicMock()
        patcher = patch('dynamo.get_table', return_value=self.mock_table)
        self.addCleanup(patcher.stop)
        patcher.start()

    def _import_handler(self):
        import importlib
        import sys
        # Ensure fresh import picks up mock
        if 'handler' in sys.modules:
            del sys.modules['handler']
        import handler
        return handler

    # ---------- POST /pins ----------

    def test_pin_building_success(self):
        handler = self._import_handler()
        self.mock_table.put_item.return_value = {}

        event = _make_event('POST', body={
            'bbl': '1001230056',
            'address': '123 Main St, New York, NY',
            'profile': {'latitude': 40.7128, 'longitude': -74.006, 'yearBuilt': '1985'},
        })
        resp = handler.lambda_handler(event, {})

        self.assertEqual(resp['statusCode'], 200)
        body = json.loads(resp['body'])
        self.assertTrue(body['pinned'])
        self.assertEqual(body['bbl'], '1001230056')
        self.mock_table.put_item.assert_called_once()
        # Verify PK/SK in stored item
        call_args = self.mock_table.put_item.call_args[1]['Item']
        self.assertEqual(call_args['PK'], 'USER#user-123')
        self.assertEqual(call_args['SK'], 'PIN#1001230056')

    def test_pin_building_missing_bbl(self):
        handler = self._import_handler()
        event = _make_event('POST', body={'address': '123 Main St'})
        resp = handler.lambda_handler(event, {})
        self.assertEqual(resp['statusCode'], 400)

    def test_pin_building_invalid_json(self):
        handler = self._import_handler()
        event = _make_event('POST')
        event['body'] = 'not-json'
        resp = handler.lambda_handler(event, {})
        self.assertEqual(resp['statusCode'], 400)

    # ---------- GET /pins ----------

    def test_list_pins_success(self):
        handler = self._import_handler()
        self.mock_table.query.return_value = {
            'Items': [
                {
                    'PK': 'USER#user-123',
                    'SK': 'PIN#1001230056',
                    'bbl': '1001230056',
                    'address': '123 Main St',
                    'pinnedAt': '2026-03-19T12:00:00+00:00',
                    'profile': {'latitude': 40.7128},
                }
            ]
        }

        event = _make_event('GET')
        resp = handler.lambda_handler(event, {})

        self.assertEqual(resp['statusCode'], 200)
        body = json.loads(resp['body'])
        self.assertEqual(len(body['buildings']), 1)
        self.assertEqual(body['buildings'][0]['bbl'], '1001230056')

    def test_list_pins_empty(self):
        handler = self._import_handler()
        self.mock_table.query.return_value = {'Items': []}

        event = _make_event('GET')
        resp = handler.lambda_handler(event, {})

        self.assertEqual(resp['statusCode'], 200)
        body = json.loads(resp['body'])
        self.assertEqual(body['buildings'], [])

    # ---------- DELETE /pins/{bbl} ----------

    def test_unpin_building_success(self):
        handler = self._import_handler()
        self.mock_table.delete_item.return_value = {}

        event = _make_event('DELETE', path_params={'bbl': '1001230056'})
        resp = handler.lambda_handler(event, {})

        self.assertEqual(resp['statusCode'], 200)
        body = json.loads(resp['body'])
        self.assertFalse(body['pinned'])
        self.mock_table.delete_item.assert_called_once_with(
            Key={'PK': 'USER#user-123', 'SK': 'PIN#1001230056'}
        )

    def test_unpin_building_missing_bbl(self):
        handler = self._import_handler()
        event = _make_event('DELETE')
        resp = handler.lambda_handler(event, {})
        self.assertEqual(resp['statusCode'], 400)

    # ---------- Auth ----------

    def test_no_auth_returns_401(self):
        handler = self._import_handler()
        event = {
            'httpMethod': 'GET',
            'requestContext': {},
            'pathParameters': {},
            'body': None,
        }
        resp = handler.lambda_handler(event, {})
        self.assertEqual(resp['statusCode'], 401)

    # ---------- OPTIONS (CORS preflight) ----------

    def test_options_returns_204(self):
        handler = self._import_handler()
        event = _make_event('OPTIONS')
        resp = handler.lambda_handler(event, {})
        self.assertEqual(resp['statusCode'], 204)


if __name__ == '__main__':
    unittest.main()
