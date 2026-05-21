import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { Construct } from "constructs";

export class HelloStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    new lambda.Function(this, "HelloWorld", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "handler.handler",
      code: lambda.Code.fromAsset("dist/stage/hello-world", {
        bundling: {
          image: cdk.DockerImage.fromRegistry("public.ecr.aws/sam/build-python3.13"),
          command: [
            "bash",
            "-lc",
            "cd /asset-input && bash ./scripts/bundle-lambda.sh services/hello-world",
          ],
        },
      }),
    });
  }
}
