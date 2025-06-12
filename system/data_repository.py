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
import json
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import BlobSasPermissions, BlobClient, generate_blob_sas
from azure.cosmosdb.table.tableservice import TableService
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import io
from .config import config
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobType


class DataRepository:
    
    def __init__(self, config: dict) -> None:
        self.config = config
        account_name = config["azure_storage_account"]
        account_key = config["azure_storage_key"]
        self.table_service = TableService(account_name=account_name, account_key=account_key)

        self.master_file_name = config['master_json_file']
        self.log_file = config["app_log"]
        self.log_buffer = io.StringIO()

        storage_con_str = config['corpdesign_storage_con_str']
        self.blob_service_client = BlobServiceClient.from_connection_string(storage_con_str)
        self.container_client = self.blob_service_client.get_container_client("purchase-order")
        self.log_blob_client = self.container_client.get_blob_client(self.log_file)

        try:
            props = self.log_blob_client.get_blob_properties()
            if props.blob_type != BlobType.AppendBlob:
                print(f"Blob exists but is of type {props.blob_type}. Replacing with AppendBlob.")
                self.log_blob_client.delete_blob()
                self.log_blob_client.create_append_blob()
                print("Append blob created.")
            else:
                print("Append blob already exists.")
        except ResourceNotFoundError:
            print("Log blob not found. Creating new append blob.")
            self.log_blob_client.create_append_blob()
        except Exception as e:
            print("Unexpected error during blob init:", str(e))


    def log_info(self, message: str):
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_buffer.write(log_entry)
        print("Log buffered:", log_entry.strip())
        self.upload_log_to_blob()

    def upload_log_to_blob(self):
        try:
            self.log_buffer.seek(0)
            log_data = self.log_buffer.getvalue()
            self.log_blob_client.append_block(data=log_data)
            print("Logs appended to blob.")
        except Exception as e:
            print("Log upload failed:", str(e))
        finally:
            self.log_buffer = io.StringIO()  # Clear buffer

    def load_json_to_blob(self, jsonString: json):
        self.container_client.upload_blob(
            name=self.master_file_name,
            data=jsonString,
            overwrite=True
        )

class MasterJSON:
    
    def __init__(self, config) -> None:

        self.config = config
        storage_con_str = config['corpdesign_storage_con_str']
        self.blob_service_client = BlobServiceClient.from_connection_string(storage_con_str)
        self.container_client = self.blob_service_client.get_container_client("purchase-order")
        self.account_key = self.config["azure_storage_key"]
        self.master_json = config['master_json_file']
        
    def _create_service_sas_blob(self, blob_client: BlobClient, account_key: str) -> str:

        # Create a SAS token that's valid for one day, as an example
        start_time = datetime.now(timezone.utc)
        expiry_time = start_time + timedelta(days=5)
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=blob_client.container_name,
            blob_name=blob_client.blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time,
            start=start_time
        )
        return expiry_time, sas_token    

    def gen_shared_link(self) -> json:

        blob_client = self.container_client.get_blob_client(self.master_json)
        download_stream = blob_client.download_blob() 
        fileReader = json.loads(download_stream.readall()) 
        return fileReader

data_repository = DataRepository(config)
master_json=MasterJSON(config)