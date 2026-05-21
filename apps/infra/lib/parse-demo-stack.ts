import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

export class ParseDemoStack extends cdk.Stack {
  public readonly uploadBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create S3 bucket for form document uploads
    this.uploadBucket = new s3.Bucket(this, "FormUploadBucket", {
      bucketName: `${cdk.Stack.of(this).account}-form-parser-uploads`,
      // Enable versioning for audit trail
      versioned: true,
      // Lifecycle rules to manage costs
      lifecycleRules: [
        {
          // Delete files older than 30 days
          expiration: cdk.Duration.days(30),
          // Delete old versions after 7 days
          noncurrentVersionExpiration: cdk.Duration.days(7),
        },
      ],
      // Enable encryption at rest
      encryption: s3.BucketEncryption.S3_MANAGED,
      // Block public access
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      // Enable CORS for web uploads
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.PUT,
            s3.HttpMethods.POST,
            s3.HttpMethods.HEAD,
          ],
          allowedOrigins: ["http://localhost:3000"],
          allowedHeaders: ["*"],
          exposedHeaders: ["ETag"], // Required for multipart upload completion
          maxAge: 3000,
        },
      ],
      // Auto delete objects when stack is destroyed (for dev/test)
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Output the bucket name for reference
    new cdk.CfnOutput(this, "UploadBucketName", {
      value: this.uploadBucket.bucketName,
      description: "S3 bucket for form document uploads",
      exportName: `${this.stackName}-UploadBucketName`,
    });

    // Output the bucket ARN
    new cdk.CfnOutput(this, "UploadBucketArn", {
      value: this.uploadBucket.bucketArn,
      description: "ARN of the upload bucket",
      exportName: `${this.stackName}-UploadBucketArn`,
    });
  }
}
