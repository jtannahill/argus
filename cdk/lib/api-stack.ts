import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as apigatewayv2 from 'aws-cdk-lib/aws-apigatewayv2';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as path from 'path';
import { Construct } from 'constructs';

interface ApiStackProps extends cdk.StackProps {
  table: dynamodb.Table;
  capturesBucket: s3.Bucket;
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly userPool: cognito.UserPool;
  public readonly notifyFn: lambda.Function;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    this.userPool = new cognito.UserPool(this, 'ArgusUserPool', {
      userPoolName: 'argus-users',
      selfSignUpEnabled: false,
      signInAliases: { email: true },
      passwordPolicy: {
        minLength: 12,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
      },
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const userPoolClient = this.userPool.addClient('ArgusClient', {
      authFlows: { userPassword: true, userSrp: true },
    });

    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'ArgusAuthorizer', {
      cognitoUserPools: [this.userPool],
    });

    this.api = new apigateway.RestApi(this, 'ArgusApi', {
      restApiName: 'Argus API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    const presignFn = new lambda.Function(this, 'PresignFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/presign/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: {
        TABLE_NAME: props.table.tableName,
        CAPTURES_BUCKET: props.capturesBucket.bucketName,
      },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });

    props.table.grantReadWriteData(presignFn);
    props.capturesBucket.grantPut(presignFn);

    const captures = this.api.root.addResource('captures');
    const presign = captures.addResource('presign');
    presign.addMethod('POST', new apigateway.LambdaIntegration(presignFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // ── Plates Lambda ──────────────────────────────────────────────────────
    const platesFn = new lambda.Function(this, 'PlatesFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/plates/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadData(platesFn);

    const platesResource = this.api.root.addResource('plates');
    const platePlate = platesResource.addResource('{plate}');
    platePlate.addMethod('GET', new apigateway.LambdaIntegration(platesFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    const plateSightings = platePlate.addResource('sightings');
    plateSightings.addMethod('GET', new apigateway.LambdaIntegration(platesFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // ── Search Lambda ──────────────────────────────────────────────────────
    const searchFn = new lambda.Function(this, 'SearchFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/search/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadData(searchFn);

    const searchResource = this.api.root.addResource('search');
    searchResource.addMethod('GET', new apigateway.LambdaIntegration(searchFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // ── Geofences Lambda ───────────────────────────────────────────────────
    const geofencesFn = new lambda.Function(this, 'GeofencesFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/geofences/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadWriteData(geofencesFn);

    const geofencesResource = this.api.root.addResource('geofences');
    geofencesResource.addMethod('POST', new apigateway.LambdaIntegration(geofencesFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    geofencesResource.addMethod('GET', new apigateway.LambdaIntegration(geofencesFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });
    const geofenceId = geofencesResource.addResource('{id}');
    geofenceId.addMethod('DELETE', new apigateway.LambdaIntegration(geofencesFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // ── Alerts Lambda ──────────────────────────────────────────────────────
    const alertsFn = new lambda.Function(this, 'AlertsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/alerts/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadData(alertsFn);

    const alertsResource = this.api.root.addResource('alerts');
    alertsResource.addMethod('GET', new apigateway.LambdaIntegration(alertsFn), {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    });

    // ── WebSocket API ──────────────────────────────────────────────────────

    // $connect Lambda
    const connectFn = new lambda.Function(this, 'WsConnectFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'connect.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/websocket/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadWriteData(connectFn);

    // $disconnect Lambda
    const disconnectFn = new lambda.Function(this, 'WsDisconnectFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'disconnect.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/websocket/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });
    props.table.grantReadWriteData(disconnectFn);

    // WebSocket API (L1 CfnApi)
    const wsApi = new apigatewayv2.CfnApi(this, 'ArgusWebSocketApi', {
      name: 'ArgusWebSocketApi',
      protocolType: 'WEBSOCKET',
      routeSelectionExpression: '$request.body.action',
    });

    // IAM role for API Gateway to invoke Lambdas
    const wsIntegRole = new iam.Role(this, 'WsIntegRole', {
      assumedBy: new iam.ServicePrincipal('apigateway.amazonaws.com'),
    });
    connectFn.grantInvoke(wsIntegRole);
    disconnectFn.grantInvoke(wsIntegRole);

    // $connect integration + route
    const connectInteg = new apigatewayv2.CfnIntegration(this, 'WsConnectInteg', {
      apiId: wsApi.ref,
      integrationType: 'AWS_PROXY',
      integrationUri: `arn:aws:apigateway:${this.region}:lambda:path/2015-03-31/functions/${connectFn.functionArn}/invocations`,
      credentialsArn: wsIntegRole.roleArn,
    });
    new apigatewayv2.CfnRoute(this, 'WsConnectRoute', {
      apiId: wsApi.ref,
      routeKey: '$connect',
      target: `integrations/${connectInteg.ref}`,
    });

    // $disconnect integration + route
    const disconnectInteg = new apigatewayv2.CfnIntegration(this, 'WsDisconnectInteg', {
      apiId: wsApi.ref,
      integrationType: 'AWS_PROXY',
      integrationUri: `arn:aws:apigateway:${this.region}:lambda:path/2015-03-31/functions/${disconnectFn.functionArn}/invocations`,
      credentialsArn: wsIntegRole.roleArn,
    });
    new apigatewayv2.CfnRoute(this, 'WsDisconnectRoute', {
      apiId: wsApi.ref,
      routeKey: '$disconnect',
      target: `integrations/${disconnectInteg.ref}`,
    });

    // Stage
    const wsStage = new apigatewayv2.CfnStage(this, 'WsStage', {
      apiId: wsApi.ref,
      stageName: 'prod',
      autoDeploy: true,
    });

    // notify Lambda — needs WEBSOCKET_ENDPOINT which references the stage URL
    const wsUrl = `https://${wsApi.ref}.execute-api.${this.region}.amazonaws.com/${wsStage.stageName}`;
    this.notifyFn = new lambda.Function(this, 'WsNotifyFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'notify.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/websocket/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: {
        TABLE_NAME: props.table.tableName,
        WEBSOCKET_ENDPOINT: wsUrl,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(this.notifyFn);
    // Allow notify Lambda to post to WebSocket connections
    this.notifyFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['execute-api:ManageConnections'],
      resources: [`arn:aws:execute-api:${this.region}:${this.account}:${wsApi.ref}/${wsStage.stageName}/POST/@connections/*`],
    }));

    new cdk.CfnOutput(this, 'ApiUrl', { value: this.api.url, exportName: 'ArgusApiUrl' });
    new cdk.CfnOutput(this, 'UserPoolId', { value: this.userPool.userPoolId, exportName: 'ArgusUserPoolId' });
    new cdk.CfnOutput(this, 'UserPoolClientId', { value: userPoolClient.userPoolClientId, exportName: 'ArgusUserPoolClientId' });
    new cdk.CfnOutput(this, 'WebSocketUrl', {
      value: `wss://${wsApi.ref}.execute-api.${this.region}.amazonaws.com/${wsStage.stageName}`,
      exportName: 'ArgusWebSocketUrl',
    });
  }
}
