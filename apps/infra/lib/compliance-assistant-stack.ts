import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecr_assets from "aws-cdk-lib/aws-ecr-assets";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";
import * as path from "path";

const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");

export class ComplianceAssistantStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const region = this.region;

    // -------------------------------------------------------
    // S3: Data assets bucket (etemplate, field prompts, embeddings)
    // -------------------------------------------------------
    const dataBucket = new s3.Bucket(this, "DataBucket", {
      bucketName: `${cdk.Stack.of(this).account}-compliance-assistant-data`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Upload data assets to S3
    new s3deploy.BucketDeployment(this, "DeployDataAssets", {
      sources: [
        s3deploy.Source.asset(
          path.join(REPO_ROOT, "data", "compliance-assistant"),
          {
            exclude: ["test-uploads", "demo", "iacuc", "mappings"],
          }
        ),
      ],
      destinationBucket: dataBucket,
      destinationKeyPrefix: "data",
    });

    // Upload etemplate separately
    new s3deploy.BucketDeployment(this, "DeployEtemplate", {
      sources: [
        s3deploy.Source.asset(
          path.join(REPO_ROOT, "apps", "compliance-assistant", "public"),
          {
            exclude: ["*", "!*.etemplate"],
          }
        ),
      ],
      destinationBucket: dataBucket,
      destinationKeyPrefix: "etemplate",
    });

    // -------------------------------------------------------
    // DynamoDB: Sessions table
    // -------------------------------------------------------
    const sessionsTable = new dynamodb.Table(this, "SessionsTable", {
      tableName: "compliance-assistant-sessions",
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
    });

    // -------------------------------------------------------
    // S3: Frontend static site bucket
    // -------------------------------------------------------
    const siteBucket = new s3.Bucket(this, "SiteBucket", {
      bucketName: `${cdk.Stack.of(this).account}-compliance-assistant-site`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // -------------------------------------------------------
    // VPC: 2 public subnets (no NAT to save cost)
    // -------------------------------------------------------
    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        {
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
      ],
    });

    // -------------------------------------------------------
    // ECS Cluster + Fargate Service
    // -------------------------------------------------------
    const cluster = new ecs.Cluster(this, "Cluster", { vpc });

    const taskDef = new ecs.FargateTaskDefinition(this, "TaskDef", {
      cpu: 512,
      memoryLimitMiB: 1024,
    });

    // Bedrock access: cross-region inference profiles + underlying foundation models
    taskDef.taskRole.addToPrincipalPolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources: [
          `arn:aws:bedrock:${region}:${this.account}:inference-profile/us.anthropic.claude-sonnet-4-6`,
          `arn:aws:bedrock:${region}:${this.account}:inference-profile/us.cohere.embed-v4:0`,
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6",
          "arn:aws:bedrock:*::foundation-model/cohere.embed-v4:0",
        ],
      })
    );

    // S3 data bucket read access
    dataBucket.grantRead(taskDef.taskRole);

    // DynamoDB access
    sessionsTable.grantReadWriteData(taskDef.taskRole);

    // Build Docker image (force amd64 for Fargate)
    const image = new ecr_assets.DockerImageAsset(this, "ApiImage", {
      directory: path.join(REPO_ROOT, "services", "compliance-assistant-api"),
      platform: ecr_assets.Platform.LINUX_AMD64,
    });

    const logGroup = new logs.LogGroup(this, "ApiLogGroup", {
      logGroupName: "/ecs/compliance-assistant-api",
      retention: logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    taskDef.addContainer("Api", {
      image: ecs.ContainerImage.fromDockerImageAsset(image),
      portMappings: [{ containerPort: 5002 }],
      environment: {
        DATA_BUCKET: dataBucket.bucketName,
        DYNAMODB_TABLE: sessionsTable.tableName,
        AWS_DEFAULT_REGION: region,
        TEMPLATE_S3_KEY: "etemplate/Initial Submission_Revision9.etemplate",
        DATA_S3_PREFIX: "data",
      },
      logging: ecs.LogDrivers.awsLogs({
        logGroup,
        streamPrefix: "api",
      }),
      healthCheck: {
        command: ["CMD-SHELL", "curl -f http://localhost:5002/health || exit 1"],
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(5),
        retries: 3,
      },
    });

    // ALB
    const alb = new elbv2.ApplicationLoadBalancer(this, "Alb", {
      vpc,
      internetFacing: true,
    });

    const listener = alb.addListener("HttpListener", {
      port: 80,
    });

    const fargateService = new ecs.FargateService(this, "Service", {
      cluster,
      taskDefinition: taskDef,
      desiredCount: 1,
      assignPublicIp: true,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      circuitBreaker: { enable: true, rollback: true },
    });

    listener.addTargets("ApiTarget", {
      port: 5002,
      protocol: elbv2.ApplicationProtocol.HTTP,
      targets: [fargateService],
      healthCheck: {
        path: "/health",
        interval: cdk.Duration.seconds(30),
        timeout: cdk.Duration.seconds(10),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    // Allow ALB to reach Fargate
    fargateService.connections.allowFrom(alb, ec2.Port.tcp(5002));

    // -------------------------------------------------------
    // CloudFront distribution
    // -------------------------------------------------------

    // OAC for S3
    const oac = new cloudfront.S3OriginAccessControl(this, "OAC", {
      signing: cloudfront.Signing.SIGV4_ALWAYS,
    });

    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(siteBucket, {
      originAccessControl: oac,
    });

    const albOrigin = new origins.HttpOrigin(alb.loadBalancerDnsName, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
    });

    const distribution = new cloudfront.Distribution(this, "Distribution", {
      defaultBehavior: {
        origin: s3Origin,
        viewerProtocolPolicy:
          cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        "/api/*": {
          origin: albOrigin,
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy:
            cloudfront.OriginRequestPolicy.ALL_VIEWER,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        },
      },
      defaultRootObject: "index.html",
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.seconds(0),
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.seconds(0),
        },
      ],
    });

    // Deploy frontend build to S3.
    // The frontend is part of a monorepo — node_modules and package-lock.json
    // live at the repo root. We use local bundling so it runs in the host
    // environment where `npm install` has already been done.
    const frontendDir = path.join(REPO_ROOT, "apps", "compliance-assistant");
    const frontendDistDir = path.join(frontendDir, "dist");

    new s3deploy.BucketDeployment(this, "DeploySite", {
      sources: [
        s3deploy.Source.asset(frontendDistDir),
      ],
      destinationBucket: siteBucket,
      distribution,
      distributionPaths: ["/*"],
    });

    // -------------------------------------------------------
    // Outputs
    // -------------------------------------------------------
    new cdk.CfnOutput(this, "SiteUrl", {
      value: `https://${distribution.distributionDomainName}`,
      description: "CloudFront URL for the compliance assistant",
    });

    new cdk.CfnOutput(this, "ApiUrl", {
      value: `http://${alb.loadBalancerDnsName}`,
      description: "ALB URL for the API (debugging)",
    });

    new cdk.CfnOutput(this, "DataBucketName", {
      value: dataBucket.bucketName,
      description: "S3 bucket for data assets",
    });

    new cdk.CfnOutput(this, "SessionsTableName", {
      value: sessionsTable.tableName,
      description: "DynamoDB sessions table",
    });
  }
}
