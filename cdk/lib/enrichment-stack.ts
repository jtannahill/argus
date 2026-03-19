import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
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
}

export class EnrichmentStack extends cdk.Stack {
  public readonly stateMachine: sfn.StateMachine;
  public readonly triggerFn: lambda.Function;

  constructor(scope: Construct, id: string, props: EnrichmentStackProps) {
    super(scope, id, props);

    // ── PlateLookup Lambda ────────────────────────────────────────────────
    const plateLookupFn = new lambda.Function(this, 'PlateLookupFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'plate_lookup.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/enrichment/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadData(plateLookupFn);

    // ── PatternDetection Lambda ───────────────────────────────────────────
    const patternFn = new lambda.Function(this, 'PatternDetectionFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'pattern_detection.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/pattern/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(patternFn);

    // ── MergeResults Lambda ───────────────────────────────────────────────
    const mergeResultsFn = new lambda.Function(this, 'MergeResultsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'merge_results.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'cp -r /asset-input/enrichment/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
          ],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });
    props.table.grantReadWriteData(mergeResultsFn);

    // ── State machine steps ───────────────────────────────────────────────

    // Branch 0: PlateLookup
    const plateLookupTask = new tasks.LambdaInvoke(this, 'PlateLookup', {
      lambdaFunction: plateLookupFn,
      outputPath: '$.Payload',
    });

    // Branch 1: VehicleClassifier stub
    const vehicleClassifierStub = new sfn.Pass(this, 'VehicleClassifier', {
      result: sfn.Result.fromObject({ make: null, model: null, year: null, color: null }),
    });

    // Branch 2: PlateRead stub
    const plateReadStub = new sfn.Pass(this, 'PlateRead', {
      result: sfn.Result.fromObject({ refinedPlate: null, confidence: 0 }),
    });

    // Parallel state: run all 3 branches concurrently
    const parallel = new sfn.Parallel(this, 'EnrichInParallel', {
      resultPath: '$.parallelResults',
    });
    parallel.branch(plateLookupTask);
    parallel.branch(vehicleClassifierStub);
    parallel.branch(plateReadStub);

    // Restructure parallel output array into named keys
    const restructure = new sfn.Pass(this, 'RestructureParallelOutput', {
      parameters: {
        'plateLookup.$': '$.parallelResults[0]',
        'vehicleClassifier.$': '$.parallelResults[1]',
        'plateRead.$': '$.parallelResults[2]',
        'plate.$': '$.plate',
        'sightingId.$': '$.sightingId',
        'timestamp.$': '$.timestamp',
        'confidence.$': '$.confidence',
        'bucket.$': '$.bucket',
        'plateImageKey.$': '$.plateImageKey',
        'vehicleImageKey.$': '$.vehicleImageKey',
      },
    });

    // MergeResults Lambda task
    const mergeTask = new tasks.LambdaInvoke(this, 'MergeResults', {
      lambdaFunction: mergeResultsFn,
      outputPath: '$.Payload',
    });

    // PatternDetection Lambda task
    const patternTask = new tasks.LambdaInvoke(this, 'PatternDetection', {
      lambdaFunction: patternFn,
      outputPath: '$.Payload',
    });

    // Chain the state machine
    this.stateMachine = new sfn.StateMachine(this, 'EnrichmentStateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(
        parallel.next(restructure).next(mergeTask).next(patternTask),
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
            'cp -r /asset-input/enrichment/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared',
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

    // S3 event notification: vehicle frame uploads trigger the pipeline.
    // Use fromBucketAttributes to create an unowned reference in this stack,
    // avoiding the cross-stack cyclic dependency that addEventNotification
    // would create when called on the DataStack-owned bucket directly.
    const capturesBucketRef = s3.Bucket.fromBucketAttributes(this, 'CapturesBucketRef', {
      bucketName: props.capturesBucket.bucketName,
      bucketArn: props.capturesBucket.bucketArn,
    });

    capturesBucketRef.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(this.triggerFn),
      { suffix: '-vehicle.jpg' },
    );

    // Outputs
    new cdk.CfnOutput(this, 'StateMachineArn', {
      value: this.stateMachine.stateMachineArn,
      exportName: 'ArgusEnrichmentStateMachineArn',
    });
  }
}
