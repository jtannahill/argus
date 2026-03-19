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

  test('creates 8 Lambda functions (presign + plates + search + geofences + alerts + ws connect + ws disconnect + ws notify)', () => {
    template.resourceCountIs('AWS::Lambda::Function', 8);
  });

  test('creates API routes for plates, search, geofences, alerts', () => {
    // Verify there are multiple API Gateway resources (captures/presign, plates/{plate},
    // plates/{plate}/sightings, search, geofences, geofences/{id}, alerts)
    const resources = template.findResources('AWS::ApiGateway::Resource');
    const resourcePaths = Object.values(resources).map(
      (r: any) => r.Properties.PathPart
    );
    expect(resourcePaths).toContain('plates');
    expect(resourcePaths).toContain('search');
    expect(resourcePaths).toContain('geofences');
    expect(resourcePaths).toContain('alerts');
    expect(resourcePaths).toContain('sightings');
    expect(resourcePaths).toContain('{id}');
  });

  test('creates WebSocket API with WEBSOCKET protocol', () => {
    template.hasResourceProperties('AWS::ApiGatewayV2::Api', {
      ProtocolType: 'WEBSOCKET',
      RouteSelectionExpression: '$request.body.action',
    });
  });

  test('creates WebSocket $connect and $disconnect routes', () => {
    template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
      RouteKey: '$connect',
    });
    template.hasResourceProperties('AWS::ApiGatewayV2::Route', {
      RouteKey: '$disconnect',
    });
  });

  test('creates WebSocket prod stage with autoDeploy', () => {
    template.hasResourceProperties('AWS::ApiGatewayV2::Stage', {
      StageName: 'prod',
      AutoDeploy: true,
    });
  });

  test('exports WebSocketUrl output', () => {
    template.hasOutput('WebSocketUrl', {});
  });
});
