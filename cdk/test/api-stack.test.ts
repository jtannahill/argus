import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { DataStack } from '../lib/data-stack';
import { ApiStack } from '../lib/api-stack';

describe('ApiStack', () => {
  const app = new cdk.App();
  const dataStack = new DataStack(app, 'TestData');
  const apiStack = new ApiStack(app, 'TestApi', {
    table: dataStack.table,
    capturesBucket: dataStack.capturesBucket,
  });
  const template = Template.fromStack(apiStack);

  test('creates Cognito user pool', () => {
    template.resourceCountIs('AWS::Cognito::UserPool', 1);
  });

  test('creates REST API Gateway', () => {
    template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
  });

  test('creates presign Lambda', () => {
    template.hasResourceProperties('AWS::Lambda::Function', {
      Runtime: 'python3.12',
      Handler: 'handler.lambda_handler',
    });
  });
});
