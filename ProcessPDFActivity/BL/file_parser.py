"""
Copyright © 2022–2023 Riverstone Infotech. All rights reserved.

CORPDESIGN Order and all related materials, including but not limited to text, graphics, 
logos, images, and software, are protected by copyright and other intellectual 
property laws. Reproduction, distribution, display, or modification of any of the 
content for any purpose without express written permission from Riverstone Infotech 
is prohibited.

For permissions and inquiries, please contact:
software@riverstonetech.com

Unauthorized use or reproduction of CORPDESIGN Order may result in legal action.
"""
import base64
import json
import logging
import base64
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
from ..Rest.resource.netsuite_int import Netsuit_SO
from ...system.Utilities import Utility
from .rules import Rules 
import random
class FileParser:

    def __init__(self, config: dict) -> None:
        self.config = config
        endpoint = config['adi_endpoint']
        key = config['adi_key']
        self._document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint, credential=AzureKeyCredential(key)
        )
   

    def extract_po(self, content_bytes: bytes,file_extension: str,filename):
        try:
            newJson = None
            nJson = None
            doc_content = base64.b64decode(content_bytes)
            
            if file_extension == ".pdf":       
                poller = self._document_analysis_client.begin_analyze_document("prebuilt-invoice", doc_content)
                order = poller.result()
                customer_name = None
                data=poller
                for invoice_document in order.documents:
                    customer_name = Rules.get_customer_name(invoice_document.fields, order)
                    if customer_name:
                        break  

            else:
                customer_name = Utility.get_cusotmer_name(doc_content)
                customer_name = Rules.adjust_customer_name(customer_name)
                data=doc_content
            if not customer_name:
                logging.info("Attempted to process an unknown file. This file is not listed in our system. Contact admin if needed.")
                return {"statusCode":404,"status":"Failure","message":"The customer variation have not been handled "}

            result_data = Rules.map_models(data, customer_name)
            result_data['po_file']={"email":{"Attachments":[{"Name":filename,"ContentBytes":content_bytes}]}}
            result_data['purchase_order'] = str(random.randint(100000, 999999))
            jsonString = json.dumps(result_data, indent=4)
            #logging.info(f"jsonString: {jsonString}")
            sJson = json.loads(jsonString)
            newJson = Netsuit_SO.so_creation(jsonString, self.config)
            with open("data.json","w") as file:
                json.dump(json.loads(jsonString),file,indent=4)
            if newJson:               
                nJson = newJson if isinstance(newJson, dict) else json.loads(newJson)
            
            if nJson and isinstance(nJson, dict): 
                status_code = nJson.get('statusCode')
                result_json = self.merge_json_data(nJson, sJson)
                #print(f"Result_Json: {result_json}")
                if status_code == 200:
                    
                    status_dict = {item['productCode'].strip(): item for item in result_json['order_line_item']}
                    print(f"status_dict: {status_dict}")
                    for sProd in result_json['order_line_items']:
                        product_code = sProd['product_code'].strip()
                        if product_code in status_dict:
                            sProd['netsuite_status'] = 'Success' if 'inserted' in status_dict[product_code] ['status']else 'Not Inserted'
                            sProd['status'] = status_dict[product_code]['status']
                            if status_dict[product_code]['status'] != 'inserted':
                                continue
                            if 'components' in status_dict[product_code] and status_dict[product_code]['components'] is not None:
                                sProd['components'] = status_dict[product_code]['components']           
                            elif 'availableQuantity' in status_dict[product_code] and status_dict[product_code]['availableQuantity'] is not None:
                                sProd['availableQuantity'] = status_dict[product_code]['availableQuantity']

                    return result_json
                                    
                else:
                    return result_json
            

        except Exception as ex:
            logging.error(f"Export PO failed to process: {ex}")
            return {"statusCode": 500, "status": "Failure", "message": "Error occurred while processing the document - " + str(ex)}

    def merge_json_data(self, json_data1, json_data2):
        if json_data1:
            merged_data = {**json_data1, **json_data2}
        else:
            logging.info('API response returned null value.')

        if "order_line_items" in json_data1 and "order_line_items" in json_data2:
            merged_data["order_line_items"] = json_data1["order_line_items"] + json_data2["order_line_items"]

        return merged_data 

class InvaidCORPDESIGNDocument(Exception): ...

class InvaidDocument(Exception): ...

class DocumentAlreadyProcessed(Exception): ...

class CORPDESIGNDocumentNotFound(Exception): ...