import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as path from 'path';
import { Construct } from 'constructs';

interface EnrichmentStackProps extends cdk.StackProps {
  table: dynamodb.Table;
  capturesBucket: s3.Bucket;
  notifyFn: lambda.Function;
}

export class EnrichmentStack extends cdk.Stack {
  public readonly stateMachine: sfn.StateMachine;
  public readonly triggerFn: lambda.Function;

  constructor(scope: Construct, id: string, props: EnrichmentStackProps) {
    super(scope, id, props);

    // ── DataAssembly Lambda ─────────────────────────────────────────────
    const dataAssemblyFn = new lambda.Function(this, 'DataAssemblyFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/data_assembly/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: {
        TABLE_NAME: props.table.tableName,
        GEOCLIENT_APP_ID: process.env.GEOCLIENT_APP_ID ?? '',
        GEOCLIENT_APP_KEY: process.env.GEOCLIENT_APP_KEY ?? '',
        SOCRATA_TOKEN: process.env.SOCRATA_TOKEN ?? '',
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(dataAssemblyFn);

    // ── StoryGenerator Lambda ───────────────────────────────────────────
    const storyFn = new lambda.Function(this, 'StoryFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/story/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(storyFn);
    storyFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: ['*'],
    }));

    // ── VisualMatch Lambda ──────────────────────────────────────────────
    const visualMatchFn = new lambda.Function(this, 'VisualMatchFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/visual_match/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: {
        TABLE_NAME: props.table.tableName,
        SAGEMAKER_ENDPOINT: 'argus-clip',
        CAPTURES_BUCKET: props.capturesBucket.bucketName,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(visualMatchFn);
    props.capturesBucket.grantRead(visualMatchFn);
    visualMatchFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['sagemaker:InvokeEndpoint'],
      resources: ['*'],
    }));

    // ── ScanAnalytics Lambda ────────────────────────────────────────────
    const scanAnalyticsFn = new lambda.Function(this, 'ScanAnalyticsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/scan_analytics/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(scanAnalyticsFn);

    // ── State machine: sequential chain ─────────────────────────────────

    const dataAssemblyTask = new tasks.LambdaInvoke(this, 'DataAssembly', {
      lambdaFunction: dataAssemblyFn,
      outputPath: '$.Payload',
    });

    const storyTask = new tasks.LambdaInvoke(this, 'StoryGenerator', {
      lambdaFunction: storyFn,
      outputPath: '$.Payload',
    });

    const visualMatchTask = new tasks.LambdaInvoke(this, 'VisualMatch', {
      lambdaFunction: visualMatchFn,
      outputPath: '$.Payload',
    });

    const scanAnalyticsTask = new tasks.LambdaInvoke(this, 'ScanAnalytics', {
      lambdaFunction: scanAnalyticsFn,
      outputPath: '$.Payload',
    });

    const notifyTask = new tasks.LambdaInvoke(this, 'NotifyClients', {
      lambdaFunction: props.notifyFn,
      outputPath: '$.Payload',
    });

    // Chain: DataAssembly → StoryGenerator → VisualMatch → ScanAnalytics → NotifyClients
    this.stateMachine = new sfn.StateMachine(this, 'EnrichmentStateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(
        dataAssemblyTask.next(storyTask).next(visualMatchTask).next(scanAnalyticsTask).next(notifyTask),
      ),
      timeout: cdk.Duration.minutes(5),
    });

    // ── Trigger Lambda ────────────────────────────────────────────────────
    this.triggerFn = new lambda.Function(this, 'TriggerFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'trigger.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/enrichment/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: {
        TABLE_NAME: props.table.tableName,
        STATE_MACHINE_ARN: this.stateMachine.stateMachineArn,
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    props.table.grantReadData(this.triggerFn);
    this.stateMachine.grantStartExecution(this.triggerFn);

    // S3 event notification: building photo uploads trigger the pipeline.
    const capturesBucketRef = s3.Bucket.fromBucketAttributes(this, 'CapturesBucketRef', {
      bucketName: props.capturesBucket.bucketName,
      bucketArn: props.capturesBucket.bucketArn,
    });

    capturesBucketRef.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(this.triggerFn),
      { suffix: '.jpg' },
    );

    // ── Aggregator Lambda (daily schedule) ──────────────────────────────
    const aggregatorFn = new lambda.Function(this, 'AggregatorFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install requests -t /asset-output/ && cp -r /asset-input/scan_analytics/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
    });
    props.table.grantReadWriteData(aggregatorFn);

    // EventBridge: daily aggregation at 2 AM UTC
    new events.Rule(this, 'DailyAggregationRule', {
      schedule: events.Schedule.expression('cron(0 2 * * ? *)'),
      targets: [new targets.LambdaFunction(aggregatorFn)],
    });

    // Outputs
    new cdk.CfnOutput(this, 'StateMachineArn', {
      value: this.stateMachine.stateMachineArn,
      exportName: 'ArgusEnrichmentStateMachineArn',
    });
  }
}
