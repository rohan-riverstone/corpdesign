import re
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import logging

class OFSOF:   
    
    def extract_part_number_and_description(self, text):
        print("text des ", text)
        text = text.replace("\n", " ").replace("- ","-").strip()

        # Updated regex pattern to correctly extract the part number
        pattern = r"^(CD-[\w-]+)\s*([A-Z]+-[A-Z]+)?\s*(.*)$"
        match = re.match(pattern, text)

        if match:
            part_number = match.group(1).rstrip(
                "-"
            )  # Remove trailing hyphen if present
            if match.group(2):  # Capture optional suffix like BLK-B
                part_number += "-" + match.group(2).strip()
            description = match.group(3).strip()
            print("part_number, description:", part_number, description)
            return part_number, description

        return None, None

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
                if items and items.value:
                    for item in items.value:
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

                        if not product_code :
                            product_code,description = self.extract_part_number_and_description(description)
                        
                        product_code = self.clean_product_code(product_code)
                        adjusted_product_code = product_code

                        order_line_items.append(
                            {
                                "product_code": adjusted_product_code,
                                "description": (
                                    description.replace("\n", "") if description else None
                                ),
                                "qty": (
                                    item.value.get("Quantity").value
                                    if item.value.get("Quantity")
                                    else None
                                ),
                                "unit_price": (
                                    item.value.get("UnitPrice").value.amount
                                    if item.value.get("UnitPrice")
                                    else None
                                ),
                                "amount": (
                                    item.value.get("Amount").value.amount
                                    if item.value.get("Amount")
                                    else None
                                ),
                                "pdf_product_code": adjusted_product_code,
                                
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