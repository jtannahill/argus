import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/data-stack';
import { EnrichmentStack } from '../lib/enrichment-stack';

describe('EnrichmentStack', () => {
  const app = new cdk.App();
  const dataStack = new DataStack(app, 'TestEnrichmentData');
  const enrichmentStack = new EnrichmentStack(app, 'TestEnrichment', {
    table: dataStack.table,
    capturesBucket: dataStack.capturesBucket,
  });
  const template = Template.fromStack(enrichmentStack);

  test('creates Step Functions state machine', () => {
    template.resourceCountIs('AWS::StepFunctions::StateMachine', 1);
  });

  test('creates plate_lookup Lambda handler', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'plate_lookup.lambda_handler',
      Runtime: 'python3.12',
    });
  });

  test('creates merge_results Lambda handler', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'merge_results.lambda_handler',
      Runtime: 'python3.12',
    });
  });

  test('creates trigger Lambda handler', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'trigger.lambda_handler',
      Runtime: 'python3.12',
    });
  });

  test('creates pattern detection Lambda handler', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Handler: 'handler.lambda_handler',
      Runtime: 'python3.12',
    });
  });
});
