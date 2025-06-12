# This function is not intended to be invoked directly. Instead it will be
# triggered by an orchestrator function.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import logging
import azure.functions as func
import json
import os
from .file_parser import (FileParser, DocumentAlreadyProcessed, CORPDESIGNDocumentNotFound)
from ...system.config import config



def main(attachment: dict):
    filename = attachment['Name']
    file_extension = os.path.splitext(filename)[1].lower()    
    fParser = FileParser(config)

    try:
        result = fParser.extract_po(attachment['ContentBytes'],file_extension,filename)
        return {"filename": filename, "result": result}
    except DocumentAlreadyProcessed as ex:
        logging.info(str(ex))
        return {"filename": filename, "error": str(ex)}
    except CORPDESIGNDocumentNotFound as ex:
        logging.info(str(ex))
        return {"filename": filename, "error": str(ex)}
    except Exception as ex:
        logging.error(str(ex))
        return {"filename": filename, "error": f"Failed to process. Reason: {str(ex)}"}
