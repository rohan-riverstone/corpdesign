import re
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import logging

class OfficeFurniture:
    def extract_product_code(self, text):        
        text = text.replace("\n", " ").strip()        
        pattern = r"\b[A-Z]*\d*-?[A-Z0-9]+(?:-[A-Z0-9]+)*\b"        
        match = re.search(pattern, text)
        
        if match:
            p_code = match.group(0).strip()
            print("Extracted product code:", p_code) 
            return p_code
        
        return None
    
    
    def extract_order_date(self, result, tolerance=0.05):
        reference_polygon = [
            (6.2126, 1.1076),
            (6.7331, 1.1076),
            (6.7331, 1.2556),
            (6.2126, 1.2509),
        ]

        ref_bounds = {
            "min_x": min(p[0] for p in reference_polygon) - tolerance,
            "max_x": max(p[0] for p in reference_polygon) + tolerance,
            "min_y": min(p[1] for p in reference_polygon) - tolerance,
            "max_y": max(p[1] for p in reference_polygon) + tolerance,
        }

        for page in result.pages:
            for item in page.lines:
                if not item.polygon:
                    continue

                bounds = {
                    "min_x": min(p[0] for p in item.polygon),
                    "max_x": max(p[0] for p in item.polygon),
                    "min_y": min(p[1] for p in item.polygon),
                    "max_y": max(p[1] for p in item.polygon),
                }

                if (
                    ref_bounds["min_x"] <= bounds["min_x"] <= ref_bounds["max_x"]
                    and ref_bounds["min_x"] <= bounds["max_x"] <= ref_bounds["max_x"]
                    and ref_bounds["min_y"] <= bounds["min_y"] <= ref_bounds["max_y"]
                    and ref_bounds["min_y"] <= bounds["max_y"] <= ref_bounds["max_y"]
                ):
                    return item.content.strip()

        return None
    
    def extract_product_code_from_table(self, order):  
        print("table lent:",len(order.tables))
        tableData = order.tables
        ext_table = []

        for table in tableData:
            raw_table = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]
            
            for cell in table.cells:
                raw_table[cell.row_index][cell.column_index] = cell.content
            
            ext_table.extend(raw_table[1:])  # Skip header row if present

        # Extract relevant rows
        extracted_items = []
        for row in ext_table:
            if len(row) >= 2 and row[0].strip().isdigit():  # Check if first value is a number (qty)
                qty = int(row[0].strip())
                description = row[1].strip()
                productCode = self.extract_product_code(description)
                extracted_items.append({"product_code": productCode, "qty": qty, "description": description})
        return extracted_items 
    
    def clean_product_code(self, product_code):
        if not product_code:
            return ""
        cleaned_code = product_code.replace("\n", "").strip()
        cleaned_code = re.sub(r"\s+", " ", cleaned_code)
        return cleaned_code

    def process_data(self, data, customer_name):
        order = data.result()
        result_data = {}
        order_line_items = []
        try:
            for invoice_document in order.documents:
                result_data["customer_name"] = customer_name
                purchase_order = invoice_document.fields.get("PurchaseOrder")
                if purchase_order and hasattr(purchase_order, "value"):
                    purchase_order = re.sub("[^A-Za-z0-9]+", "", purchase_order.value)
                else:
                    invoice_id_field = invoice_document.fields.get("InvoiceId")
                    purchase_order = (
                        invoice_id_field.value
                        if invoice_id_field and hasattr(invoice_id_field, "value")
                        else None
                    )

                if purchase_order:
                    result_data["purchase_order"] = purchase_order

                invoice_date = invoice_document.fields.get("InvoiceDate")
                if invoice_date:
                    result_data["invoice_date"] = invoice_date.value.strftime("%m/%d/%Y")
                else:
                    result_data["invoice_date"]= self.extract_order_date(order)
                    
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                if invoice_document.fields.get("ShippingAddressRecipient"): 
                    result_data['shipping_address'][0]['addressee'] = invoice_document.fields.get("ShippingAddressRecipient").value.replace('\n'," ")

                # vendor_address = invoice_document.fields.get("VendorAddress")
                # if vendor_address:
                #     result_data["billing_address"] = Utility.splitted_address(
                #         vendor_address.value.to_dict()
                #     )                         
                product_code_list = (
                    self.extract_product_code_from_table(order)
                )               
                for product in product_code_list:  # Iterate over the list of dictionaries
                    adjusted_product_code = product.get("product_code")  # Use .get() to avoid KeyErrors
                    description = product.get("description")
                    qty = product.get("qty")

                    order_line_items.append(
                        {
                            "product_code": adjusted_product_code,
                            "description": description.replace("\n", "").replace(adjusted_product_code,"") if description else None,
                            "qty": qty,
                            "pdf_product_code": adjusted_product_code,  # Duplicate value, is this needed?
                        }
                    )

                result_data["order_line_items"] = product_mapper.find_best_match(
                    order_line_items
                )

            return result_data
        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )
            