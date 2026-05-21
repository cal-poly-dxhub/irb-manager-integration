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

export class ComplianceAssistantV2Stack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const region = this.region;

    // -------------------------------------------------------
    // S3: Data assets bucket (etemplate, field prompts, embeddings)
    // -------------------------------------------------------
    const dataBucket = new s3.Bucket(this, "DataBucketV2", {
      bucketName: `${cdk.Stack.of(this).account}-compliance-assistant-v2-data`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // Upload data assets to S3
    new s3deploy.BucketDeployment(this, "DeployDataAssetsV2", {
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
    new s3deploy.BucketDeployment(this, "DeployEtemplateV2", {
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
    const sessionsTable = new dynamodb.Table(this, "SessionsTableV2", {
      tableName: "compliance-assistant-v2-sessions",
      partitionKey: { name: "PK", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "SK", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: "ttl",
    });

    // -------------------------------------------------------
    // S3: Frontend static site bucket
    // -------------------------------------------------------
    const siteBucket = new s3.Bucket(this, "SiteBucketV2", {
      bucketName: `${cdk.Stack.of(this).account}-compliance-assistant-v2-site`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // -------------------------------------------------------
    // VPC: 2 public subnets (no NAT to save cost)
    // -------------------------------------------------------
    const vpc = new ec2.Vpc(this, "VpcV2", {
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
    const cluster = new ecs.Cluster(this, "ClusterV2", { vpc });

    const taskDef = new ecs.FargateTaskDefinition(this, "TaskDefV2", {
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
    const image = new ecr_assets.DockerImageAsset(this, "ApiImageV2", {
      directory: path.join(REPO_ROOT, "services", "compliance-assistant-api"),
      platform: ecr_assets.Platform.LINUX_AMD64,
    });

    const logGroup = new logs.LogGroup(this, "ApiLogGroupV2", {
      logGroupName: "/ecs/compliance-assistant-v2-api",
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
    const alb = new elbv2.ApplicationLoadBalancer(this, "AlbV2", {
      vpc,
      internetFacing: true,
    });

    const listener = alb.addListener("HttpListenerV2", {
      port: 80,
    });

    const fargateService = new ecs.FargateService(this, "ServiceV2", {
      cluster,
      taskDefinition: taskDef,
      desiredCount: 1,
      assignPublicIp: true,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      circuitBreaker: { enable: true, rollback: true },
    });

    listener.addTargets("ApiTargetV2", {
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
    const oac = new cloudfront.S3OriginAccessControl(this, "OACV2", {
      signing: cloudfront.Signing.SIGV4_ALWAYS,
    });

    const s3Origin = origins.S3BucketOrigin.withOriginAccessControl(siteBucket, {
      originAccessControl: oac,
    });

    const albOrigin = new origins.HttpOrigin(alb.loadBalancerDnsName, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTP_ONLY,
    });

    const distribution = new cloudfront.Distribution(this, "DistributionV2", {
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
    const frontendDir = path.join(REPO_ROOT, "apps", "compliance-assistant");
    const frontendDistDir = path.join(frontendDir, "dist");

    new s3deploy.BucketDeployment(this, "DeploySiteV2", {
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
    new cdk.CfnOutput(this, "SiteUrlV2", {
      value: `https://${distribution.distributionDomainName}`,
      description: "CloudFront URL for the compliance assistant v2",
    });

    new cdk.CfnOutput(this, "ApiUrlV2", {
      value: `http://${alb.loadBalancerDnsName}`,
      description: "ALB URL for the API v2 (debugging)",
    });

    new cdk.CfnOutput(this, "DataBucketNameV2", {
      value: dataBucket.bucketName,
      description: "S3 bucket for data assets v2",
    });

    new cdk.CfnOutput(this, "SessionsTableNameV2", {
      value: sessionsTable.tableName,
      description: "DynamoDB sessions table v2",
    });
  }
}
