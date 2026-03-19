import * as cdk from 'aws-cdk-lib';
import * as sagemaker from 'aws-cdk-lib/aws-sagemaker';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as path from 'path';
import { Construct } from 'constructs';

interface MlStackProps extends cdk.StackProps {
  table: dynamodb.Table;
  trainingBucket: s3.Bucket;
  capturesBucket: s3.Bucket;
}

export class MlStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MlStackProps) {
    super(scope, id, props);

    // SageMaker execution role
    const sagemakerRole = new iam.Role(this, 'SageMakerRole', {
      assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSageMakerFullAccess'),
      ],
    });
    props.trainingBucket.grantReadWrite(sagemakerRole);
    props.capturesBucket.grantRead(sagemakerRole);

    // Explicit S3 access for SageMaker model validation
    sagemakerRole.addToPolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject', 's3:ListBucket'],
      resources: [
        props.trainingBucket.bucketArn,
        `${props.trainingBucket.bucketArn}/*`,
      ],
    }));

    // CLIP embedding model endpoint (Serverless Inference)
    const clipModel = new sagemaker.CfnModel(this, 'ClipModel', {
      executionRoleArn: sagemakerRole.roleArn,
      primaryContainer: {
        image: `763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1-cpu-py310`,
        modelDataUrl: `s3://${props.trainingBucket.bucketName}/models/clip-embedding/model.tar.gz`,
      },
    });
    clipModel.node.addDependency(sagemakerRole);

    const clipEndpointConfig = new sagemaker.CfnEndpointConfig(this, 'ClipEndpointConfig', {
      productionVariants: [{
        modelName: clipModel.attrModelName,
        variantName: 'AllTraffic',
        serverlessConfig: {
          maxConcurrency: 3,
          memorySizeInMb: 3072,
        },
      }],
    });

    new sagemaker.CfnEndpoint(this, 'ClipEndpoint', {
      endpointConfigName: clipEndpointConfig.attrEndpointConfigName,
      endpointName: 'argus-clip',
    });

    // Nightly aggregation batch Lambda
    const aggregationBatchFn = new lambda.Function(this, 'AggregationBatchFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'batch_aggregation.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: ['bash', '-c', 'pip install requests -t /asset-output/ && cp -r /asset-input/scan_analytics/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared'],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
    });
    props.table.grantReadWriteData(aggregationBatchFn);

    // EventBridge: nightly aggregation at 4 AM UTC
    new events.Rule(this, 'NightlyAggregationRule', {
      schedule: events.Schedule.expression('cron(0 4 * * ? *)'),
      targets: [new targets.LambdaFunction(aggregationBatchFn)],
    });

    // Retrain trigger Lambda (kicks off SageMaker Training Jobs)
    const retrainFn = new lambda.Function(this, 'RetrainTriggerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'retrain_trigger.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../ml'), {
        exclude: ['*.tar.gz', 'model_data/**', '*.whl'],
      }),
      environment: {
        TRAINING_BUCKET: props.trainingBucket.bucketName,
        SAGEMAKER_ROLE_ARN: sagemakerRole.roleArn,
      },
      timeout: cdk.Duration.seconds(30),
    });
    retrainFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['sagemaker:CreateTrainingJob'],
      resources: ['*'],
    }));

    // EventBridge: weekly retrain on Sundays at 6 AM UTC
    new events.Rule(this, 'WeeklyRetrainRule', {
      description: 'Weekly CLIP model retraining',
      schedule: events.Schedule.expression('cron(0 6 ? * SUN *)'),
      targets: [new targets.LambdaFunction(retrainFn)],
    });
  }
}
