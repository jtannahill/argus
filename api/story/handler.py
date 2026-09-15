"""Step Functions task — generate a building narrative via Bedrock Claude.

Reads the PROFILE record from DynamoDB, builds a structured prompt, calls
Bedrock (claude-sonnet), and writes the parsed result as a STORY record.
Returns {bbl, headline, narrative, funFacts}.
"""

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import building_pk, profile_sk, story_sk

# Bedrock model to use for narrative generation
BEDROCK_MODEL_ID = 'anthropic.claude-sonnet-4-5'

# Lazy Bedrock client — initialised once per container
_bedrock = None


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
    return _bedrock


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    bbl = event.get('bbl', '').strip()
    if not bbl:
        raise ValueError('Event must include a non-empty "bbl" field')

    table = get_table()
    pk = building_pk(bbl)

    # -- Fetch PROFILE from DynamoDB -------------------------------------------
    resp = table.get_item(Key={'PK': pk, 'SK': profile_sk()})
    profile = resp.get('Item')
    if not profile:
        raise LookupError(f'No PROFILE found for BBL {bbl}')

    # -- Build prompt -----------------------------------------------------------
    prompt = _build_prompt(bbl, profile)

    # -- Call Bedrock -----------------------------------------------------------
    raw_response = _invoke_bedrock(prompt)
    parsed = _parse_bedrock_response(raw_response)

    headline = parsed.get('headline', '')
    narrative = parsed.get('narrative', '')
    fun_facts = parsed.get('funFacts', [])

    # -- Write STORY record -----------------------------------------------------
    story_item = {
        'PK': pk,
        'SK': story_sk(),
        'bbl': bbl,
        'headline': headline,
        'narrative': narrative,
        'funFacts': fun_facts,
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'modelId': BEDROCK_MODEL_ID,
    }
    table.put_item(Item=story_item)

    return {
        'bbl': bbl,
        'headline': headline,
        'narrative': narrative,
        'funFacts': fun_facts,
    }


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(bbl: str, profile: dict) -> str:
    """Assemble a building-facts block and return the full Bedrock prompt."""

    def _str(key: str, default: str = 'Unknown') -> str:
        val = profile.get(key)
        if val is None or val == '':
            return default
        return str(val)

    address = _str('address')
    borough_name = _borough_name(_str('borough', ''))
    year_built = _str('yearbuilt')
    stories = _str('numfloors')
    bldg_class = _str('bldgclass')
    zone = _str('zonedist1')

    # Landmark details (nested dict if present)
    landmark_info = profile.get('landmark')
    if isinstance(landmark_info, dict):
        landmark_name = landmark_info.get('buildingName', '')
        designated_date = (landmark_info.get('designatedDate', '') or '')[:10]
        landmark_text = f'{landmark_name} (designated {designated_date})' if landmark_name else 'Yes'
    else:
        landmark_text = 'No'

    # Architect / style from profile (may come from PLUTO extended fields)
    architect = _str('architect', 'Unknown')
    style = _str('bldgstyle', _str('style', 'Unknown'))

    facts = (
        f'Address: {address}, {borough_name}\n'
        f'Year built: {year_built}\n'
        f'Stories: {stories}\n'
        f'Building class: {bldg_class}\n'
        f'Zoning: {zone}\n'
        f'Architect: {architect}\n'
        f'Style: {style}\n'
        f'Landmark designation: {landmark_text}'
    )

    prompt = (
        'You are an expert architectural historian writing engaging building profiles for a '
        'New York City intelligence platform. Given the following building facts, write a '
        'short, captivating narrative in the style of a high-quality magazine feature.\n\n'
        f'Building Facts:\n{facts}\n\n'
        'Respond with a JSON object only (no markdown fences, no extra text) with exactly '
        'these fields:\n'
        '  "headline"  — a punchy 8-12 word headline\n'
        '  "narrative" — 3-4 sentences of vivid narrative prose\n'
        '  "funFacts"  — an array of 3 short, surprising facts as strings\n'
    )
    return prompt


def _borough_name(borough_code: str) -> str:
    mapping = {
        '1': 'Manhattan',
        '2': 'Bronx',
        '3': 'Brooklyn',
        '4': 'Queens',
        '5': 'Staten Island',
    }
    return mapping.get(str(borough_code).strip(), 'New York City')


# ---------------------------------------------------------------------------
# Bedrock integration
# ---------------------------------------------------------------------------

def _invoke_bedrock(prompt: str) -> str:
    """Call Bedrock InvokeModel and return the raw text content."""
    bedrock = _get_bedrock()

    body = json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 500,
        'messages': [
            {
                'role': 'user',
                'content': prompt,
            }
        ],
    })

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType='application/json',
        accept='application/json',
        body=body,
    )

    response_body = json.loads(response['body'].read())
    # Claude Messages API response shape: content[0].text
    return response_body['content'][0]['text']


def _parse_bedrock_response(raw: str) -> dict:
    """Parse the JSON object returned by Claude.

    Claude is instructed to return raw JSON, but defensively strip any
    accidental markdown fences before parsing.
    """
    text = raw.strip()
    # Strip optional ```json ... ``` fences
    if text.startswith('```'):
        lines = text.splitlines()
        # Drop first and last fence lines
        inner = lines[1:-1] if lines[-1].strip().startswith('```') else lines[1:]
        text = '\n'.join(inner).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Graceful degradation — return raw text as narrative
        parsed = {
            'headline': 'A Building With Stories to Tell',
            'narrative': raw[:500],
            'funFacts': [],
        }

    # Ensure expected keys exist with sensible defaults
    return {
        'headline': str(parsed.get('headline', '')),
        'narrative': str(parsed.get('narrative', '')),
        'funFacts': list(parsed.get('funFacts', [])),
    }
