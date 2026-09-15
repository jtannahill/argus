import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/data-stack';
import { ApiStack } from '../lib/api-stack';
import { EnrichmentStack } from '../lib/enrichment-stack';

describe('EnrichmentStack', () => {
  const app = new cdk.App();
  const dataStack = new DataStack(app, 'TestEnrichmentData');
  const apiStack = new ApiStack(app, 'TestEnrichmentApi', {
    table: dataStack.table,
    capturesBucket: dataStack.capturesBucket,
  });
  const enrichmentStack = new EnrichmentStack(app, 'TestEnrichment', {
    table: dataStack.table,
    capturesBucket: dataStack.capturesBucket,
    notifyFn: apiStack.notifyFn,
  });
  const template = Template.fromStack(enrichmentStack);

  test('creates Step Functions state machine', () => {
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
  });

  test('creates DataAssembly Lambda', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'handler.lambda_handler',
      Runtime: 'python3.12',
    });
  });

  test('creates StoryGenerator Lambda with Bedrock permissions', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: Match.objectLike({
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'bedrock:InvokeModel',
          }),
        ]),
      }),
    });
  });

  test('creates VisualMatch Lambda with SageMaker permissions', () => {
    template.hasResourceProperties('AWS::IAM::Policy', {
      PolicyDocument: Match.objectLike({
        Statement: Match.arrayWith([
          Match.objectLike({
            Action: 'sagemaker:InvokeEndpoint',
          }),
        ]),
      }),
    });
  });

  test('creates trigger Lambda handler', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'trigger.lambda_handler',
      Runtime: 'python3.12',
    });
  });

  test('creates daily aggregation EventBridge rule at 2 AM UTC', () => {
    template.hasResourceProperties('AWS::Events::Rule', {
      ScheduleExpression: 'cron(0 2 * * ? *)',
    });
  });

  test('does not create PlateLookup or PatternDetection Lambdas', () => {
    const functions = template.findResources('AWS::Lambda::Function');
    const handlers = Object.values(functions).map((r: any) => r.Properties.Handler);
    expect(handlers).not.toContain('plate_lookup.lambda_handler');
    expect(handlers).not.toContain('pattern_detection.lambda_handler');
    expect(handlers).not.toContain('merge_results.lambda_handler');
  });
});
