# This function is not intended to be invoked directly. Instead it will be
# triggered by an HTTP starter function.
# Before running this sample, please:
# - create a Durable activity function (default name is "Hello")
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import logging
import json

from azure.durable_functions import DurableOrchestrationContext, Orchestrator
from ..system.data_repository import data_repository,master_json
from ..Templates.views import  render_purchase_order_summary,render_no_valid_attachments_message 
from ..system.Utilities import Utility
import os 

ALLOWED_EXTENSIONS = {".pdf", ".xls", ".xlsx"}


def get_valid_attachments(attachments):
    valid_attachments=[]
    for attachment in attachments:
        filename = attachment['Name']
        file_extension = os.path.splitext(filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            logging.warning(f"Skipping file {filename} with unsupported extension {file_extension}.")
            continue 
        valid_attachments.append(attachment)
        

    return valid_attachments

def orchestrator_function(context: DurableOrchestrationContext):
    input_data = context.get_input()

    if input_data is None:
        logging.error("No input received by orchestrator.")
        return {"error": "No input received."}

    from_email = input_data.get("from")
    attachments = input_data.get("attachments")

    if not attachments:
        data_repository.log_info(f"[Error] {from_email} - No valid attachments were provided. Please upload files with the following extensions: .pdf, .xls, .xlsx.")
        return {
            "data": render_no_valid_attachments_message(),
            "subject": "No valid attachments found"
        }

    valid_attachments = get_valid_attachments(attachments)
    if not valid_attachments:
        data_repository.log_info(f"[Error] {from_email} - No valid attachments were provided. Please upload files with the following extensions: .pdf, .xls, .xlsx.")
        return {
            "data": render_no_valid_attachments_message(),
            "subject": "No valid attachments found"
        }

    parallel_tasks = [context.call_activity('ProcessPDFActivity', name) for name in valid_attachments]

    result = yield context.task_all(parallel_tasks)
    result, subject = Utility.generate_total(result)

    for res in result:
        filename = res['filename']
        result_ = res['result']['status']
        message = res['result']['message']
        if res['result']['statusCode'] == 200:
            data_repository.log_info(
                f"[Info] From: {from_email} - File: {filename} - Result: {result_} - "
                f"Message: {message} - SalesOrder {res['result']['orderNumber']} - "
                f"OrderLineItems {res['result']['order_line_items']}"
            )
        else:
            data_repository.log_info(
                f"[Error] From: {from_email} - File: {filename} - Result: {result_} - Message: {message}"
            )

    final_json_data = json.dumps(result, indent=4)
    data_repository.load_json_to_blob(final_json_data)

    result = render_purchase_order_summary(result)

    return {
        "data": result,
        "subject": subject
    }



main = Orchestrator.create(orchestrator_function)