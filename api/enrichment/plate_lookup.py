"""Plate lookup enrichment — stubbed initially."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def lambda_handler(event, context):
    plate = event.get('plate', '')
    return {
        'plate': plate,
        'registration': {
            'make': None,
            'model': None,
            'year': None,
            'color': None,
            'state': None,
            'vin': None,
            'owner': None,
            'address': None,
            'source': 'stub',
        },
    }
