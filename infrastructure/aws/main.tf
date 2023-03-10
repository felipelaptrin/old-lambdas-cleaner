###########################
###  MODULES
###########################

##################
## S3
##################
module "s3_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "v3.6.0"

  bucket = local.bucket_name
  acl    = "private"

  versioning = {
    enabled = true
  }
}

##################
## LAMBDA
##################
module "lambda_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "v4.7.1"

  function_name = "old-lambdas-cleaner"
  description   = "Puts old lambdas in a quarantine state and then deletes them"
  handler       = "main.lambda_handler"
  runtime       = "python3.9"

  create_package = false
  s3_existing_package = {
    bucket = local.bucket_name
    key    = "old-lambdas-cleaner.zip"
  }

  create_role = false
  lambda_role = aws_iam_role.lambda.arn

  environment_variables = {
    ENVIRONMENT              = "DEV"
    SLACK_SECRET_MANAGER_ARN = aws_secretsmanager_secret_version.slack.arn
    SLACK_CHANNEL            = "notifications"
    THRESHOLD_OLD_LAMBDA     = "60"
  }

  tags = {
    Name      = "old-lambdas-cleaner"
    Terraform = "TRUE"
  }
}

##################
## EVENTBRIDGE
##################
module "eventbridge" {
  source  = "terraform-aws-modules/eventbridge/aws"
  version = "v1.17.0"

  create_bus = false

  rules = {
    lambda = {
      description         = "Trigger Lambda weekly"
      schedule_expression = "cron(0 10 ? * 2 *)"
    }
  }

  targets = {
    lambda = [
      {
        name  = "old-lambdas-cleaner"
        arn   = module.lambda_function.lambda_function_arn
        input = jsonencode({ "action" : "checkOldLambdas" })
      }
    ]
  }
}

###########################
###  RESOURCES
###########################

##################
## SECRET MANAGER
##################
resource "aws_secretsmanager_secret" "slack" {
  name        = "slack-token"
  description = "Stores credential of the Slack Bot."
}

resource "aws_secretsmanager_secret_version" "slack" {
  secret_id     = aws_secretsmanager_secret.slack.id
  secret_string = data.sops_file.secrets.data["SLACK_TOKEN"]
}

##################
## IAM
##################
resource "aws_iam_policy" "lambda" {
  name        = "old-lambdas-cleaner"
  path        = "/"
  description = "Allows Lambda to block/delete old Lambdas"

  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        "Sid" : "AllowLambdaActions",
        "Effect" : "Allow",
        "Action" : [
          "lambda:GetFunction",
          "lambda:ListFunctions",
          "lambda:ListTags",
          "lambda:TagResource",
          "lambda:UntagResource",
          "lambda:DeleteFunction",
          "lambda:PutFunctionConcurrency"
        ],
        "Resource" : [
          "*"
        ]
      },
      {
        "Sid" : "AllowCloudWatchActions",
        "Effect" : "Allow",
        "Action" : [
          "logs:DescribeLogStreams"
        ],
        "Resource" : [
          "*"
        ]
      },
      {
        "Sid" : "SecretsManagerActions",
        "Effect" : "Allow",
        "Action" : [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ],
        "Resource" : [
          "${aws_secretsmanager_secret_version.slack.arn}"
        ]
      }
    ]
  })

  tags = {
    Terraform = "TRUE"
  }
}


resource "aws_iam_role" "lambda" {
  name        = "old-lambdas-cleaner"
  description = "Allows Lambda to block/delete old Lambdas"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    aws_iam_policy.lambda.arn
  ]

  tags = {
    Terraform = "TRUE"
  }
}

##################
## EVENTBRIDGE
##################
resource "aws_cloudwatch_event_target" "this" {
  arn  = module.lambda_function.lambda_function_arn
  rule = module.eventbridge.eventbridge_rule_ids["lambda"]
}


##################
## LAMBDA
##################
resource "aws_lambda_permission" "this" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = module.eventbridge.eventbridge_rule_arns["lambda"]
}
