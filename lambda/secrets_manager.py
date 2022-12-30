import base64
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s | %(levelname)s: %(message)s", level=logging.INFO)


secrets_manager = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION"))


def get_slack_secret() -> str:
    logger.info("Retriving Slack secret...")
    try:
        response = secrets_manager.get_secret_value(
            SecretId=os.getenv("SLACK_SECRET_MANAGER_ARN"),
        )
    except Exception as e:
        raise e
    else:
        if "SecretString" in response:
            secret = response["SecretString"]
        else:
            secret = base64.b64decode(response["SecretBinary"])

    return secret
