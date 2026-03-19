#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { DataStack } from '../lib/data-stack';
import { ApiStack } from '../lib/api-stack';
import { EnrichmentStack } from '../lib/enrichment-stack';

const app = new cdk.App();
const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'us-east-1' };

const data = new DataStack(app, 'ArgusData', { env });
new ApiStack(app, 'ArgusApi', { env, table: data.table, capturesBucket: data.capturesBucket });
new EnrichmentStack(app, 'ArgusEnrichment', { env, table: data.table, capturesBucket: data.capturesBucket });
