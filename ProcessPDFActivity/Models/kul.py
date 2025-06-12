import re
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import logging

class Kul:
    
    def clean_product_code(self, product_code):
        cleaned_code = product_code.replace("\n", "").strip()
        return cleaned_code if cleaned_code != product_code else product_code

    def adjust_product_code(self, product_code):
        product_rules = {"CD-307H": "CD-307HB (2)"}
        return product_rules.get(product_code, product_code)

    def extract_product_code_from_table(self, order):
        part_numbers = []

        for table in order.tables:
            rows = {}
            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = {}
                rows[cell.row_index][cell.column_index] = cell.content

            for row_index in sorted(rows.keys()):
                vendor_part = rows[row_index].get(0, None)  # Extract Vendor Part column
                if vendor_part and vendor_part.lower() != "vendor part":
                    part_numbers.append(vendor_part.strip())

        return part_numbers

    def clean_description(self, description):
        """Cleans description by removing `/`, `'`, and formatting quotes properly."""
        if not description:
            return None
        # Remove / and ' characters
        cleaned_desc = re.sub(r"[/'\"]", "", description)
        # Ensure proper formatting for dimensions (e.g., 30\"Dx66\"Wx29\"H → 30Dx66Wx29H)
        cleaned_desc = re.sub(r"\\", "", cleaned_desc)
        return cleaned_desc.strip()

    def process_data(self, data, customer_name):
        order = data.result()
        result_data = {}
        order_line_items = []
        try :    
            for invoice_document in order.documents:
                result_data["customer_name"] = "Kul Office Furniture"
                purchase_order = invoice_document.fields.get("PurchaseOrder")

                if purchase_order and hasattr(purchase_order, "value"):
                    purchase_order = re.sub(r"[^A-Za-z0-9]+", "", purchase_order.value)
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

                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                result_data['shipping_address'][0]['addressee'] = invoice_document.fields.get("ShippingAddressRecipient").value.replace('\n'," ")

                vendor_address = invoice_document.fields.get("VendorAddress")
                if vendor_address:
                    result_data["billing_address"] = Utility.splitted_address(
                        vendor_address.value.to_dict()
                    )

                items = invoice_document.fields.get("Items")
                extracted_part_numbers = self.extract_product_code_from_table(order)

                if items and items.value:
                    item_list = list(items.value)
                    for i, item in enumerate(item_list):
                        product_code = (
                            item.value.get("ProductCode")
                            .value.replace(".", "")
                            .replace("\n", "")
                            if item.value.get("ProductCode")
                            else ""
                        )
                        description = (
                            item.value.get("Description").value
                            if item.value.get("Description")
                            else ""
                        )
                        description = re.sub(r"[/'\"]", "", description).replace("\n", "")
                        quantity = (
                            item.value.get("Quantity").value
                            if item.value.get("Quantity")
                            else 0
                        )
                        unit_price = (
                            item.value.get("UnitPrice").value.amount
                            if item.value.get("UnitPrice")
                            else 0
                        )
                        amount = (
                            item.value.get("Amount").value.amount
                            if item.value.get("Amount")
                            else 0
                        )

                        if not product_code and extracted_part_numbers:
                            product_code = extracted_part_numbers.pop(
                                0
                            )  # Assign the next extracted part number

                        product_code = self.clean_product_code(product_code)

                        order_line_items.append(
                            {
                                "product_code": product_code,
                                "description": description,
                                "qty": quantity,
                                "unit_price": unit_price,
                                "amount": amount,
                                "pdf_product_code": product_code,
                                
                            }
                        )

                result_data["order_line_items"] = order_line_items
            print("Before Mapping - ", result_data)
            result_data["order_line_items"] = product_mapper.find_best_match(
                result_data["order_line_items"]
            )
            print("After Mapping - ", result_data)
            return result_data
        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )