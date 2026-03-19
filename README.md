# Argus

**Building Intelligence for NYC** — Point your phone at any building and instantly see its story, ownership, value, violations, and development potential.

Argus turns your iPhone camera into a building x-ray. GPS, compass heading, altitude, and 3D ray casting identify which building you're looking at. Eight NYC public data APIs assemble the full picture. AI generates the narrative.

## How It Works

1. **Point** — Open the app, aim at a building. The targeting reticle locks on.
2. **Identify** — GPS + heading + 3D ray casting resolves the building in <1 second.
3. **Discover** — Bottom sheet slides up with 5 tabs of intelligence.
4. **Pin** — Save buildings to your personal collection for later review.

## What You See

| Tab | Data Source | What's There |
|-----|-----------|--------------|
| **Story** | Bedrock AI + PLUTO | AI-generated building narrative, fun facts, notable tenants |
| **Owner** | ACRIS (legals + master + parties) | LLC name, purchase price, sale date, related properties |
| **Value** | PLUTO + DOF | Assessed value, zoning, FAR, air rights (unused sq ft), tax status |
| **Violations** | DOB + HPD | Open violations, complaints, stop work orders |
| **Permits** | DOB | Active permits, estimated costs, contractors |

## Features

- **3D Ray Casting** — Uses PLUTO building geometry (floors, dimensions) to determine which building the camera ray hits first. Tall buildings correctly occlude shorter ones.
- **4 Range Modes** — Nearby (30m), Street (100m), Block (300m), Far (800m). Heading cone auto-narrows with distance for precision skyline sniping.
- **Air Rights Ghost** — Toggle to visualize unused development rights as a translucent overlay above the building. Shows potential additional floors and square footage.
- **Diplomatic Detection** — Flags foreign government/consular properties and tax-exempt buildings from ownership patterns.
- **Altitude + Pitch** — Barometric altimeter + gyroscope pitch projects camera ray to ground level when elevated (rooftops, high floors).
- **Address Search** — Geoclient v2 typeahead for manual building lookup.
- **Pin Collection** — Save buildings to your personal map. Synced across devices.
- **CLIP Visual Matching** — Camera photos generate embeddings for building fingerprinting. Index grows with every scan.
- **Scan Analytics** — Aggregate heat maps of building interest. Which blocks are people looking at?

## Architecture

```
iPhone (Swift 6)
  ├── Camera + GPS + Compass + Altimeter + Gyroscope
  ├── BuildingIdentifier → POST /identify
  ├── Bottom Sheet (5 tabs)
  └── Explore Map (pinned buildings)

AWS Backend (CDK v2)
  ├── API Gateway → Lambda (Python 3.12)
  │   ├── /identify — GPS + heading + 3D ray cast → building candidates
  │   ├── /buildings/{bbl} — full building detail
  │   ├── /pins — pin/unpin/list saved buildings
  │   └── /search/address — Geoclient v2 typeahead
  ├── Step Functions — data assembly → story gen → visual match → analytics
  ├── DynamoDB — single-table (BLDG#, SCAN#, GEO#, HEAT#, PIN#)
  ├── SageMaker Serverless — CLIP ViT-B/32 embeddings
  ├── Bedrock (Claude) — AI story generation
  └── CloudFront — dashboard + static assets

NYC Public Data (all free)
  ├── GeoClient v2 — address → BBL resolution
  ├── PLUTO — zoning, FAR, year built, building class, owner
  ├── ACRIS — ownership, sales, mortgages (legals + master + parties)
  ├── DOB — permits, violations, certificates
  ├── HPD — housing complaints, violations
  ├── LPC — landmark designations
  ├── DOF — assessed values, tax class
  └── 311 — service requests
```

## Stack

**iOS:** Swift 6, AVFoundation, CoreLocation, CoreMotion, ARKit-ready, MapKit

**Backend:** CDK v2, Lambda (Python 3.12), DynamoDB, Step Functions, API Gateway, Cognito, S3, EventBridge

**ML:** SageMaker Serverless (CLIP ViT-B/32), Bedrock (Claude Haiku)

**Frontend:** Next.js 16, Mapbox GL JS, Tailwind CSS

## Data Products

The app is free. The aggregate, anonymized scan data is the product:

- **Interest Heat Maps** — which buildings and blocks get the most attention
- **Intent Signals** — tab depth reveals investor vs tourist vs inspector
- **Street-Level Imagery** — continuously updated building photos from user scans
- **Neighborhood Trajectories** — scan velocity as a gentrification leading indicator

## Live

- **API:** `https://7c46jp99ta.execute-api.us-east-1.amazonaws.com/prod/`
- **Dashboard:** `https://d4tb4yqt8i4xo.cloudfront.net`
- **iOS:** Build from Xcode (`ios/Argus/Argus.xcodeproj`)
