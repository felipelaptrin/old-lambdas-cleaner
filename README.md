# old-lambdas-cleaner

## Description
The code in this repository is responsible for deactivating and deleting old Lambdas in AWS.

## Architecture

![The architecture of the project](/docs/architecture.png)

## Environment Variables
The following environment variables must be used in this code:

| **Environment Variable** | **Description**                                                                                            | **Example**                                                                    |
|--------------------------|------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| AWS_REGION               | The AWS region where the AWS Lambdas were created. This is automatically passed by AWS Lambda when AWS starts the Lambda execution.       | us-west-2                                                                      |
| ENVIRONMENT              | Name of the environment that this project will run. It accepts values: DEV, STAGING, or PROD                 | PROD                                                                           |
| SLACK_SECRET_MANAGER_ARN | ARN of Secret Manager that contains the Slack API Token used to send Slack messages                        | `arn:aws:secretsmanager:us-east-1:111111111111:secret:slack-token-H1M3Yw`               |
| SLACK_CHANNEL            | Name of the Slack channel that will receive the message                                                    | notification-channel                                                                    |
| THRESHOLD_OLD_LAMBDA     | How many days since the last Lambda log event in the CloudWatch Group the Lambda will be considered as old | 180                                                                            |


## Actions
This code is responsible for:

1) Get information (name, last time it ran, tags...) about all Lambdas in a given region
2) Block traffic (concurrency execution will be set to zero) to all Lambdas that are `THRESHOLD_OLD_LAMBDA` days old and mark Lambda for deletion by adding `deleteAfter` (it will be blocked for 90 days and after that, it will delete the Lambda) and `isBlockedForInactivity` tags to control the process.
3) Send a message via Slack informing the Lambdas that were blocked and Lambdas that will be deleted soon (in 14 days).
4) Unblocking Lambda by triggering the Lambda manually specifying the Lambda that needs to be unblocked. This will add a tag called `THRESHOLD_OLD_LAMBDA` that will increase the threshold value to two times the value of the `THRESHOLD_OLD_LAMBDA` environment variable. For example: if the environment variable `THRESHOLD_OLD_LAMBDA` is set to 180 days and the Lambda is unblocked, it will increase the `THRESHOLD_OLD_LAMBDA` of this Lambda to 360 days. If in the future it gets unblocked again it will increase the `THRESHOLD_OLD_LAMBDA` tag of this Lambda to 540 days and so on.

## How to unblock a function
When the latest log of a Lambda is at least `THRESHOLD_OLD_LAMBDA` days apart from today, the Lambda will be blocked (concurrent execution will be zero). After 90 days this Lambda will be deleted automatically.

There are cases where the Lambda should not be deleted and should be unblocked. In this case, the Lambda can be manually triggered.

### 1) Export the Lambda function name and AWS region

Example:
```sh
export FUNCTION_NAME=my-important-lambda
export AWS_REGION=us-west-2
```

### 2) Trigger the lambda

```sh
aws lambda invoke --function-name lambda-cleanup --payload "{\"action\":\"unblockLambda\",\"functionName\":\"$FUNCTION_NAME\"}" --region $AWS_REGION --cli-binary-format raw-in-base64-out /tmp/lambda-response.json > /tmp/invoke-return.json
echo "\n\nInvoke return..."
cat /tmp/invoke-return.json
echo "\nLambda response..."
cat /tmp/lambda-response.json
```

## Notes
1) The code only considers Lambdas that contain a CloudWatch Group to log the events. This means that, if the Lambda was never triggered or does not log into a CloudWatch Group, it will never be detected by this code.