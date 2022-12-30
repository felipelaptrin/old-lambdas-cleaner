import logging
import os
from typing import Dict, List

from secrets_manager import get_slack_secret
from slack_sdk import WebClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s | %(levelname)s: %(message)s", level=logging.INFO)


def assert_environment_variables_are_set(env_vars: List[str]) -> None:
    not_set = []

    for key in env_vars:
        if not os.getenv(key):
            not_set.append(key)

    if not_set:
        error = f"Event sent it not correct! Missing value for: {not_set}"
        logger.error(error)
        raise Exception(error)


def assert_inputs_were_given(event: dict, event_keys: List[str]) -> None:
    not_set = []

    for key in event_keys:
        if not event.get(key):
            not_set.append(key)

    if not_set:
        error = f"Event sent it not correct! Missing value for: {not_set}"
        logger.error(error)
        raise Exception(error)


def send_slack_message(lambdas_to_block: List[str], lambdas_to_delete_soon: Dict[str, str]):
    slack_bot_token = get_slack_secret()
    client = WebClient(token=slack_bot_token)
    message = f"The `old-lambdas-cleaner` Lambda Function detected old Lambdas in the *{os.getenv('ENVIRONMENT')}* account that apparently are not in use!\n\n"

    if lambdas_to_block or lambdas_to_delete_soon:
        if lambdas_to_block:
            lambdas_to_block.sort()
            message += f"*Lambdas that were blocked (can't be triggered):*\n"
            for function_name in lambdas_to_block:
                message += f"\t `{function_name}`\n"

        if lambdas_to_delete_soon:
            message += f"*Lambdas that are already blocked and will be deleted soon:*\n"
            for function_name, date_to_delete in lambdas_to_delete_soon.items():
                message += f"\t*Name*: `{function_name}` \t *Date*: `{date_to_delete}`\n"

        message += f"\nIf you want to unblock or cancel the Lambda deletion check the README documentation for instructions."

        try:
            result = client.chat_postMessage(
                channel=os.getenv("SLACK_CHANNEL"),
                text=message,
            )
            logger.info(result)
        except Exception as e:
            raise e
    logger.info("There is no need to send Slack message!")
