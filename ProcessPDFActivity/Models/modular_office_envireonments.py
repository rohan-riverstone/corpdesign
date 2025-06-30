import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper

class Modular_Office_Environment:

    def process_data(self, data, customer_name, address_tolerance=0.05, phone_tolerance=0.5):
        try:
            order = data.result()
            result_data = {
                "customer_name": customer_name,
            }

            ref_bounds_phone = {
                "min_x": 0.2435 - phone_tolerance,
                "max_x": 1.0219 + phone_tolerance,
                "min_y": 1.1124 - phone_tolerance,
                "max_y": 1.2174 + phone_tolerance,
            }

            phone_pattern=re.compile(r"\+1\s?\d{10}\b")

            # Loop through pages and lines to extract billing address lines
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
                            print(primary_phone_number)


            # Extract shipping address from invoice document fields
            for invoice_document in order.documents:
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                result_data['shipping_address'][0]['addressee'] = invoice_document.fields.get("ShippingAddressRecipient").value.replace('\n'," ") + f", {primary_phone_number}"
                vendor_address = invoice_document.fields.get("VendorAddress")
                if vendor_address:
                    result_data["billing_address"] = Utility.splitted_address(
                        vendor_address.value.to_dict()
                    )

            
            # Extract and format invoice date
            date_value = order.documents[0].fields['InvoiceDate'].value
            result_data['invoice_date'] = date_value.strftime("%m/%d/%Y")

            # Extract purchase order number
            result_data['purchase_order'] = order.documents[0].fields['PurchaseOrder'].value

            # Extract order line items from table
            result_data["order_line_items"] = self.extract_from_table(order.to_dict())
            result_data["order_line_items"]=product_mapper.find_best_match(result_data["order_line_items"])

            # Print or log the result for debugging
            print(f"result_data: {result_data}")
            return result_data

        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}",exc_info=True
            )

    def extract_from_table(self,data):
        order_line_items = []
        for table in data["tables"]:
            if table["column_count"] == 5:
                rows = {}
                for cell in table["cells"]:
                    if "kind" in cell.keys() and cell["kind"] == "columnHeader" or cell["content"] == "Service":
                        continue
                    row_idx = cell["row_index"]
                    col_idx = cell["column_index"]
                    # Clean up cell content
                    content = cell["content"]
                    if row_idx not in rows:
                        rows[row_idx] = {}
                    rows[row_idx][col_idx] = content
                sorted_row_indices = sorted(rows.keys())

                for idx, row_idx in enumerate(sorted_row_indices):
                    row = [rows[row_idx].get(col_idx, "") for col_idx in range(7)]
                    # Skip empty rows
                    if not row or all(cell.strip() == "" for cell in row) or row[0] == '':
                        continue

                    # Map row data to item dictionary
                    product_code_match = re.search(r"\bCD-[A-Za-z0-9-]+\b", row[1].strip())
                    product_code = product_code_match.group() if product_code_match else ""

                    cleaned_text = re.sub(r"\bCD-[A-Za-z0-9-]+\b", "", row[1].strip())

                    description = " ".join(cleaned_text.split())

                    item={
                        "product_code":product_code,
                        "description":description,
                        "qty":int(row[2]),
                        "unit_price":float(row[3].replace(',','')),
                        "amount":float(row[4].replace(',','')),
                        "pdf_product_code":product_code,
                    }
                    order_line_items.append(item)
        return order_line_items