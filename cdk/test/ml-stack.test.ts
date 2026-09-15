import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/data-stack';
import { MlStack } from '../lib/ml-stack';

describe('MlStack', () => {
  const app = new cdk.App();
  const dataStack = new DataStack(app, 'TestData');
  const mlStack = new MlStack(app, 'TestMl', {
    table: dataStack.table,
    trainingBucket: dataStack.trainingBucket,
    capturesBucket: dataStack.capturesBucket,
  });
  const template = Template.fromStack(mlStack);

  test('creates single CLIP SageMaker endpoint', () => {
    template.resourceCountIs('AWS::SageMaker::Endpoint', 1);
  });

  test('creates CLIP endpoint with correct name', () => {
    template.hasResourceProperties('AWS::SageMaker::Endpoint', {
      EndpointName: 'argus-clip',
    });
  });

  test('does not create VehicleClassifier endpoint', () => {
    const endpoints = template.findResources('AWS::SageMaker::Endpoint');
    const endpointNames = Object.values(endpoints).map((r: any) => r.Properties.EndpointName);
    expect(endpointNames).not.toContain('argus-vehicle-classifier');
    expect(endpointNames).not.toContain('argus-plate-read');
  });

  test('CLIP model uses clip-embedding model data', () => {
    const models = template.findResources('AWS::SageMaker::Model');
    const modelDataUrls = Object.values(models).map(
      (r: any) => JSON.stringify(r.Properties.PrimaryContainer.ModelDataUrl)
    );
    expect(modelDataUrls.some((url: string) => url.includes('clip-embedding/model.tar.gz'))).toBe(true);
  });

  test('creates NightlyAggregationRule EventBridge schedule', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(0 4 * * ? *)',
    });
  });

  test('creates EventBridge rule for weekly retraining', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(0 6 ? * SUN *)',
    });
  });
});
