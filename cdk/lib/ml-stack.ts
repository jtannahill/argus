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

    // Plate Read endpoint (Serverless Inference)
    const plateReadModel = new sagemaker.CfnModel(this, 'PlateReadModel', {
      executionRoleArn: sagemakerRole.roleArn,
      primaryContainer: {
        image: `763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1-cpu-py310`,
        modelDataUrl: `s3://${props.trainingBucket.bucketName}/models/plate-read/model.tar.gz`,
      },
    });

    const plateReadEndpointConfig = new sagemaker.CfnEndpointConfig(this, 'PlateReadEndpointConfig', {
      productionVariants: [{
        modelName: plateReadModel.attrModelName,
        variantName: 'AllTraffic',
        serverlessConfig: {
          maxConcurrency: 5,
          memorySizeInMb: 4096,
        },
      }],
    });

    new sagemaker.CfnEndpoint(this, 'PlateReadEndpoint', {
      endpointConfigName: plateReadEndpointConfig.attrEndpointConfigName,
      endpointName: 'argus-plate-read',
    });

    // Vehicle Classifier endpoint (Serverless Inference)
    const vehicleModel = new sagemaker.CfnModel(this, 'VehicleClassifierModel', {
      executionRoleArn: sagemakerRole.roleArn,
      primaryContainer: {
        image: `763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.1-cpu-py310`,
        modelDataUrl: `s3://${props.trainingBucket.bucketName}/models/vehicle-classifier/model.tar.gz`,
      },
    });

    const vehicleEndpointConfig = new sagemaker.CfnEndpointConfig(this, 'VehicleEndpointConfig', {
      productionVariants: [{
        modelName: vehicleModel.attrModelName,
        variantName: 'AllTraffic',
        serverlessConfig: {
          maxConcurrency: 10,
          memorySizeInMb: 4096,
        },
      }],
    });

    new sagemaker.CfnEndpoint(this, 'VehicleClassifierEndpoint', {
      endpointConfigName: vehicleEndpointConfig.attrEndpointConfigName,
      endpointName: 'argus-vehicle-classifier',
    });

    // Nightly pattern batch Lambda
    const patternBatchFn = new lambda.Function(this, 'PatternBatchFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'batch_patterns.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../api'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: ['bash', '-c', 'cp -r /asset-input/pattern/* /asset-output/ && cp -r /asset-input/shared /asset-output/shared'],
        },
      }),
      environment: { TABLE_NAME: props.table.tableName },
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
    });
    props.table.grantReadWriteData(patternBatchFn);

    // EventBridge: nightly batch at 4 AM UTC
    new events.Rule(this, 'NightlyPatternRule', {
      schedule: events.Schedule.expression('cron(0 4 * * ? *)'),
      targets: [new targets.LambdaFunction(patternBatchFn)],
    });

    // Retrain trigger Lambda (kicks off SageMaker Training Jobs)
    const retrainFn = new lambda.Function(this, 'RetrainTriggerFn', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'retrain_trigger.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../ml')),
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
      schedule: events.Schedule.expression('cron(0 6 ? * SUN *)'),
      targets: [new targets.LambdaFunction(retrainFn)],
    });
  }
}
