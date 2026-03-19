import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { FrontendStack } from '../lib/frontend-stack';

describe('FrontendStack', () => {
  const app = new cdk.App();
  const stack = new FrontendStack(app, 'TestFrontend');
  const template = Template.fromStack(stack);

  test('creates S3 bucket for static assets', () => {
    template.resourceCountIs('AWS::S3::Bucket', 1);
  });

  test('creates CloudFront distribution', () => {
    template.resourceCountIs('AWS::CloudFront::Distribution', 1);
  });
});
