import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import json

class Mr_Office_Furniture:

    def extract_clean_product_code(self,code):
        for i in code:
            if "CD-" in i:
                code.remove(i)
                return [i]+code
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
                for idx, row_idx in enumerate(sorted_row_indices[1:]):
                    row = [rows[row_idx].get(col_idx, "") for col_idx in range(5)]
                    if not row or all(cell.strip() == "" for cell in row) or row[0]=='':
                        continue
                    row[1]=row[1].replace("- ",'-')
                    content=self.extract_clean_product_code(row[1].split(" "))
                    product_code=content[0]
                    description=" ".join(content[1:])
                    if description.strip() and description.strip()[0]=='(':
                        description=''
                    item={
                        "product_code": product_code,
                        "description": description,
                        "qty": int(row[2]),
                        "unit_price":float(row[3].replace(',','')),
                        "amount": float(row[4].replace(',','')),
                        "pdf_product_code": product_code
                    }
                    order_line_items.append(item)
        return order_line_items
    
    def process_data(self,data,customer_name):
        try:
            primary_phone_number = ''
            # If data is a poller, get the result and convert to dict
            if hasattr(data, "result"):
                order = data.result()
                analyze_result = order.to_dict()
                
            else:
                analyze_result = data
                order = None

            result_data = {
                "customer_name": customer_name
            }

            # Extract purchase order number from table if available
            po=order.documents[0].fields['PurchaseOrder'].value
            if po:
                result_data["purchase_order"] = po
            else:
                result_data["purchase_order"] = None

            # get the invoice date
            date_value = order.documents[0].fields['InvoiceDate'].value
            result_data['invoice_date'] = date_value.strftime("%m/%d/%Y")

            #extract phonenumber and address
            
            ref_bounds_phone = {
                "min_x": 0.7115- 0.5,
                "max_x": 1.7573+ 0.5,
                "min_y": 1.4562- 0.5,
                "max_y": 1.6233+ 0.5,
            }

                        
            ref_bounds_address = {
                "min_x": 0.5205,
                "max_x": 1.977,
                "min_y": 2.1484,
                "max_y": 2.7118,
            }

            address_lines = []
            zip_code = None
            zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")
            phone_pattern = re.compile(r'\b\d{3}-\d{3}-\d{4}\b')

            for page in order.pages:
                for item in page.lines:
                    if not item.polygon:
                        continue

                    bounds = {
                        "min_x": min(p.x for p in item.polygon),
                        "max_x": max(p.x for p in item.polygon),
                        "min_y": min(p.y for p in item.polygon),
                        "max_y": max(p.y for p in item.polygon),
                    }

                    in_bounds = (
                        ref_bounds_address["min_x"] <= bounds["min_x"] <= ref_bounds_address["max_x"]
                        and ref_bounds_address["min_x"] <= bounds["max_x"] <= ref_bounds_address["max_x"]
                        and ref_bounds_address["min_y"] <= bounds["min_y"] <= ref_bounds_address["max_y"]
                        and ref_bounds_address["min_y"] <= bounds["max_y"] <= ref_bounds_address["max_y"]
                    )

                    if in_bounds:
                        line_text = item.content.strip().replace("-", "")
                        address_lines.append(line_text)

                        zip_match = zip_pattern.search(item.content)
                        if zip_match:
                            zip_code = zip_match.group()

                    phone_match = phone_pattern.search(item.content)
                    if phone_match:
                        found_phone = phone_match.group().strip()

                        if (
                            ref_bounds_phone["min_x"] <= bounds["min_x"] <= ref_bounds_phone["max_x"]
                            and ref_bounds_phone["min_x"] <= bounds["max_x"] <= ref_bounds_phone["max_x"]
                            and ref_bounds_phone["min_y"] <= bounds["min_y"] <= ref_bounds_phone["max_y"]
                            and ref_bounds_phone["min_y"] <= bounds["max_y"] <= ref_bounds_phone["max_y"]
                        ):
                            primary_phone_number = found_phone
            print(f"Address: {address_lines}")


             # Extract addresses if order is available
            for invoice_document in order.documents:
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(), flag=True
                    )[0]
                    recipient = invoice_document.fields.get("ShippingAddressRecipient")
                    if recipient:
                        result_data['shipping_address']['addressee'] = recipient.value.replace('\n', " ")+', '+ primary_phone_number
                                    
            result_data["billing_address"]={
                "address1": address_lines[0],
                "address2": address_lines[1]+" "+address_lines[2],
                "city": address_lines[3].split(',')[0].strip(),
                "state": address_lines[3].split(',')[1].strip().split(" ")[0],
                "zip_code": zip_code
            }

           

            result_data["order_line_items"] = self.extract_data_from_table(analyze_result)
            result_data["order_line_items"]=product_mapper.find_best_match(result_data["order_line_items"])
            print(f"result: {result_data}")

            return result_data

        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}",exc_info=True
            )
            