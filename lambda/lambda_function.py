import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Union

import boto3
from botocore.exceptions import ClientError

function = boto3.client("lambda", region_name=os.getenv("AWS_REGION"))
cloudwatch = boto3.client("logs", region_name=os.getenv("AWS_REGION"))


logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s | %(levelname)s: %(message)s", level=logging.INFO)


def get_all_function_names() -> List[str]:
    logger.info("Getting all Lambdas functions...")

    kwargs = {}
    all_functions = []
    while True:
        response = function.list_functions(**kwargs)
        functions = [info["FunctionName"] for info in response["Functions"]]
        all_functions = all_functions + functions

        if response.get("NextMarker"):
            kwargs = {"Marker": response["NextMarker"]}
        else:
            break

    logger.info("All Lambdas functions retrieved!")
    return all_functions


def get_lambdas_tags(lambdas: List[str]) -> Dict[str, Dict[str, str]]:
    logger.info("Getting all Lambdas tags...")
    lambdas_tags = {}

    for function_name in lambdas:
        response = function.get_function(FunctionName=function_name)
        if response.get("Tags"):
            lambdas_tags[function_name] = response["Tags"]
        else:
            lambdas_tags[function_name] = {}

    logger.info("Tags in all lambdas retrieved!")
    return lambdas_tags


def get_last_execution_date(function_name: str) -> Union[datetime, None]:
    log_group = f"/aws/lambda/{function_name}"
    try:
        response = cloudwatch.describe_log_streams(
            logGroupName=log_group,
            orderBy="LastEventTime",
            limit=1,
            descending=True,
        )
        log_stream_name = response["logStreams"][0]["logStreamName"]
        log_stream_date = log_stream_name[:10]
        date = datetime.strptime(log_stream_date, "%Y/%m/%d")
        return date
    except ClientError as e:
        return None
    except Exception as e:
        logger.error(e)
        raise Exception(e)


def get_old_lambdas_info() -> Dict[str, Dict[str, str]]:
    lambdas = get_all_function_names()
    lambdas_tags = get_lambdas_tags(lambdas)

    today = datetime.now()

    logger.info("Getting all old lambdas info...")
    old_lambdas_info = {}
    for function_name in lambdas:
        last_execution_date = get_last_execution_date(function_name)
        if not last_execution_date:
            continue

        if lambdas_tags[function_name].get("THRESHOLD_OLD_LAMBDA"):
            diff_in_days = (today - last_execution_date).days
            if diff_in_days >= int(lambdas_tags[function_name]["THRESHOLD_OLD_LAMBDA"]):
                old_lambdas_info[function_name] = lambdas_tags[function_name]
        else:
            diff_in_days = (today - last_execution_date).days
            if diff_in_days >= int(os.getenv("THRESHOLD_OLD_LAMBDA")):
                old_lambdas_info[function_name] = lambdas_tags[function_name]

    logger.info("Old lambdas retrieved successfuly!")
    return old_lambdas_info


def get_old_lambdas_to_tag_and_block(
    old_lambdas_info: Dict[str, Dict[str, str]]
) -> Dict[str, Dict[str, str]]:
    logger.info("Getting old Lambdas that need to be tagged...")
    deletion_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

    tags_to_add = {}
    for function_name, tags in old_lambdas_info.items():
        if not tags.get("deleteAfter"):
            tags_to_add[function_name] = {
                "deleteAfter": deletion_date,
                "isBlockedForInactivity": "true",
            }
    logger.info("Old Lambdas that need to be tagged were retrieved!")

    return tags_to_add


def tag_and_block_old_lambdas(old_lambdas_info: Dict[str, Dict[str, str]]) -> None:
    account_id = boto3.client("sts").get_caller_identity().get("Account")
    old_lambdas_to_tag = get_old_lambdas_to_tag_and_block(old_lambdas_info)

    logger.info("Tagging old Lambdas...")
    for function_name, tags in old_lambdas_to_tag.items():
        function.tag_resource(
            Resource=f"arn:aws:lambda:{os.getenv('AWS_REGION')}:{account_id}:function:{function_name}",
            Tags=tags,
        )
    logger.info("Lambdas were tagged successfully!")
    logger.info("Blocking Lambdas from being triggered...")
    for function_name in old_lambdas_to_tag:
        function.put_function_concurrency(
            FunctionName=function_name,
            ReservedConcurrentExecutions=0,
        )
    logger.info("Blocking Lambdas from being triggered finished with success!")

    return list(old_lambdas_to_tag.keys())


def remove_lambda_block(function_name: str) -> None:
    account_id = boto3.client("sts").get_caller_identity().get("Account")

    logger.info("Removing 'deleteAfter' and 'isBlockedForInactivity' tags...")
    function.untag_resource(
        Resource=f"arn:aws:lambda:{os.getenv('AWS_REGION')}:{account_id}:function:{function_name}",
        TagKeys=["deleteAfter", "isBlockedForInactivity"],
    )
    logger.info("The tag removal was a success!")

    logger.info(f"Increase THRESHOLD_OLD_LAMBDA value for the {function_name} Lambda")
    tags = get_lambdas_tags([function_name])
    if tags[function_name].get("THRESHOLD_OLD_LAMBDA"):
        current_threshold = tags[function_name]["THRESHOLD_OLD_LAMBDA"]
        threshold_old_lambda = int(current_threshold) + int(os.getenv("THRESHOLD_OLD_LAMBDA"))
    else:
        threshold_old_lambda = int(os.getenv("THRESHOLD_OLD_LAMBDA")) * 2
    function.tag_resource(
        Resource=f"arn:aws:lambda:{os.getenv('AWS_REGION')}:{account_id}:function:{function_name}",
        Tags={"THRESHOLD_OLD_LAMBDA": str(threshold_old_lambda)},
    )
    logger.info(f"THRESHOLD_OLD_LAMBDA increased!")

    logger.info("Increasing Lambda concurrency...")
    function.put_function_concurrency(
        FunctionName=function_name,
        ReservedConcurrentExecutions=1000,
    )
    logger.info("Lambda concurrency increased!")


def get_lambdas_that_will_be_deleted_soon(
    old_lambdas_info: Dict[str, Dict[str, str]]
) -> Dict[str, str]:
    logger.info("Geting Lambdas that will be deleted soon...")
    lambdas = {}
    today = datetime.now()

    for function_name, tags in old_lambdas_info.items():
        if tags.get("deleteAfter"):
            date_to_delete = datetime.strptime(tags["deleteAfter"], "%Y-%m-%d")
            diff_days = (date_to_delete - today).days
            if 0 <= diff_days <= 14:
                lambdas[function_name] = tags["deleteAfter"]

    logger.info("Lambdas that will be deleted soon were retrieved with success!")
    return lambdas


def delete_old_lambdas(old_lambdas_info: Dict[str, Dict[str, str]]) -> None:
    logger.info("Deleting old lambdas...")

    lambdas_to_delete = []
    for function_name, tags in old_lambdas_info.items():
        if tags.get("deleteAfter"):
            date_to_delete = datetime.strptime(tags["deleteAfter"], "%Y-%m-%d")
            if datetime.now() > date_to_delete:
                lambdas_to_delete.append(function_name)

    for function_name in lambdas_to_delete:
        function.delete_function(FunctionName=function_name)

    logger.info(f"The following lambdas were deleted: {lambdas_to_delete}")
