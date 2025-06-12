# This function an HTTP starter function for Durable Functions.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable activity function (default name is "Hello")
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt
 
import logging
import azure.functions as func
import azure.durable_functions as df
import json

async def main(req: func.HttpRequest, starter: str) -> func.HttpResponse:
    client = df.DurableOrchestrationClient(starter)  

    try:
        body = req.get_json()

        # Ensure 'email' key exists and has 'Attachments'
        email_body = body.get("email")
        from_=email_body.get("From")
        if not email_body or "Attachments" not in email_body:
            logging.error("Invalid request: Missing 'email' or 'Attachments' key.")
            return func.HttpResponse("Invalid request: Missing 'email' or 'Attachments' key.", status_code=400)

        all_attachments = email_body["Attachments"]

        # Ensure attachments is a list
        if not isinstance(all_attachments, list):
            logging.error("Invalid request: 'Attachments' should be a list.")
            return func.HttpResponse("Invalid request: 'Attachments' should be a list.", status_code=400)
        orchestration_input = {
            "from": from_,
            "attachments": all_attachments
        }
        instance_id = await client.start_new("DurableFunctionsOrchestrator", None, orchestration_input)  
        logging.info(f"Started orchestration with ID = {instance_id}")

        return client.create_check_status_response(req, instance_id)

    except json.JSONDecodeError:
        logging.error("Invalid JSON format in request body.")
        return func.HttpResponse("Invalid JSON format.", status_code=400)

    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return func.HttpResponse(f"Internal Server Error: {str(e)}", status_code=500)
