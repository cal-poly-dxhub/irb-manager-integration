#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ComplianceAssistantStack } from "../lib/compliance-assistant-stack";
import { ComplianceAssistantV2Stack } from "../lib/compliance-assistant-v2-stack";

const app = new cdk.App();

const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// Legacy stacks — only instantiate if explicitly requested via context
// e.g. cdk deploy -c legacy=true ResearchComplianceHello
if (app.node.tryGetContext("legacy")) {
  const { HelloStack } = require("../lib/hello-stack");
  const { ParseDemoStack } = require("../lib/parse-demo-stack");
  new HelloStack(app, "ResearchComplianceHello", { env });
  new ParseDemoStack(app, "ResearchComplianceParseDemo", { env });
}

new ComplianceAssistantStack(app, "ComplianceAssistantStack", { env });
new ComplianceAssistantV2Stack(app, "ComplianceAssistantV2Stack", { env });
