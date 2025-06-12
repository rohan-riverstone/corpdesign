import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import json

class CommercialDesignServices:

    def extract_data_from_table(self,result):
    
        order_line_items = []
        for table in result.get("tables", []):
            if table.get("columnCount", table.get("column_count", 0)) == 5:
                rows = {}
                for cell in table["cells"]:
                    if cell.get("kind") == "columnHeader":
                        continue
                    row_idx = cell.get("rowIndex", cell.get("row_index"))
                    col_idx = cell.get("columnIndex", cell.get("column_index"))
                    content = cell.get("content", "").replace("\n", " ").strip()
                    if row_idx not in rows:
                        rows[row_idx] = {}
                    rows[row_idx][col_idx] = content
                sorted_row_indices = sorted(rows.keys())
                # Skip the first two rows and leave the last row
                for idx, row_idx in enumerate(sorted_row_indices[2:-1]):
                    row = [rows[row_idx].get(col_idx, "") for col_idx in range(5)]
                    if not row or all(cell.strip() == "" for cell in row):
                        continue
                    item = {
                        "Line": row[0],
                        "Qty Ordered": row[1],
                        "Catalog Number/Description": row[2],
                        "Unit Price": row[3],
                        "Extended Amount": row[4]
                    }
                    order_line_items.append(item)
        return order_line_items
    
    def process_data(self, data, customer_name):
        try:
            # If data is a poller, get the result and convert to dict
            if hasattr(data, "result"):
                order = data.result()
                analyze_result = order.to_dict()
                with open("/home/jijin/roh/cropdesign/datas.json", "w") as file:
                    json.dump(analyze_result, file, indent=4)
            else:
                analyze_result = data
                order = None

            result_data = {
                "customer_name": customer_name,
                "order_line_items": self.extract_data_from_table(analyze_result)
            }

            # get the invoice date
            match = None
            pages = analyze_result.get("pages", [])
            for page in pages:
                lines = page.get("lines", [])
                for items in lines:
                    date_pattern = re.compile(r"\b(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/(\d{4})\b")
                    match = date_pattern.search(items["content"])
                    if match:
                        break
            result_data["invoice_date"] = match.group() if match else None

            # Extract addresses if order is available
            if order:
                for invoice_document in order.documents:
                    shipping_address = invoice_document.fields.get("ShippingAddress")
                    if shipping_address:
                        result_data["shipping_address"] = Utility.splitted_address(
                            shipping_address.value.to_dict(), flag=True
                        )
                        recipient = invoice_document.fields.get("ShippingAddressRecipient")
                        if recipient:
                            result_data['shipping_address'][0]['addressee'] = recipient.value.replace('\n', " ")
                    vendor_address = invoice_document.fields.get("VendorAddress")
                    if vendor_address:
                        result_data["billing_address"] = Utility.splitted_address(
                            vendor_address.value.to_dict()
                        )

            # Extract purchase order number from table if available
            tables = analyze_result.get("tables", [])
            if tables and "cells" in tables[0] and len(tables[0]["cells"]) > 1:
                po = tables[0].get("cells", [])
                po_num = po[1]["content"].replace("\n", " ").strip()
                result_data["purchase_order"] = po_num
            else:
                result_data["purchase_order"] = None

            return result_data

        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )