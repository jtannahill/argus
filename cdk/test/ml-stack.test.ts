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

  test('creates SageMaker endpoints', () => {
    template.resourceCountIs('AWS::SageMaker::Endpoint', 2);
  });

  test('creates EventBridge rule for weekly retraining', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(0 6 ? * SUN *)',
    });
  });

  test('creates nightly pattern batch Lambda', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(0 4 * * ? *)',
    });
  });
});
