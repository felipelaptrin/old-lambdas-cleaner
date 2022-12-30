import logging
import os

from helpers import (
    assert_environment_variables_are_set,
    assert_inputs_were_given,
    send_slack_message,
)
from lambda_function import (
    delete_old_lambdas,
    get_lambdas_that_will_be_deleted_soon,
    get_old_lambdas_info,
    remove_lambda_block,
    tag_and_block_old_lambdas,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s | %(levelname)s: %(message)s", level=logging.INFO)


def lambda_handler(event, context):
    logger.info(f"Input event: {event}")
    assert_environment_variables_are_set(
        [
            "SLACK_SECRET_MANAGER_ARN",
            "SLACK_CHANNEL",
            "AWS_REGION",
            "THRESHOLD_OLD_LAMBDA",
            "ENVIRONMENT",
        ]
    )
    assert os.getenv("ENVIRONMENT") in [
        "DEV",
        "STAGING",
        "PROD",
    ], "Allowed values for ENVIRONMENT are: DEV, STAGING, PROD"
    try:
        if event["action"] == "checkOldLambdas":
            old_lambdas_info = get_old_lambdas_info()
            lambdas_to_block = tag_and_block_old_lambdas(old_lambdas_info)
            lambdas_to_delete_soon = get_lambdas_that_will_be_deleted_soon(old_lambdas_info)
            delete_old_lambdas(old_lambdas_info)
            send_slack_message(lambdas_to_block, lambdas_to_delete_soon)

        elif event["action"] == "unblockLambda":
            assert_inputs_were_given(event, ["functionName"])
            remove_lambda_block(event["functionName"])
            return {"message": f"Function '{event['functionName']}' is now unblocked!"}

        else:
            return {
                "message": "The input event must contain a key called 'action' that contains one of the following values: 'checkOldLambdas', 'unblockLambda'."
            }

    except Exception as e:
        logger.error(e)
        return {"message": "Something went wrong!", "error": str(e)}


lambda_handler({"action": "checkOldLambdas"}, "")
