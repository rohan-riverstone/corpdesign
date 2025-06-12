import re
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import logging

class BocaFurniture:    
    
    def clean_product_code(self, product_code):
        # Replace newlines and strip extra spaces
        cleaned_code = product_code.replace("\n", "").strip()
        cleaned_code = re.sub(
            r"\s+", " ", cleaned_code
        )  # Replace multiple spaces with a single space
        return cleaned_code

    def extract_part_number_and_description(self, text):
        # Pattern to match both CD- and CD_ formats as part numbers
        pattern = r"\b(CD[-_][\w-]+)\b\s*(.*)"

        match = re.match(pattern, text)
        if match:
            part_number = match.group(1)
            description = match.group(2).strip() if match.group(2) else None
            if "MIELE" in part_number:
                part_number = part_number.replace("MIELE", "")
                if description:
                    description += "MIELE"
                else:
                    description = "MIELE"
            return part_number.replace("_", "-"), description
        return None, None

    def process_data(self, data, customer_name):
        order = data.result()
        result_data = {}
        order_line_items = []
        try :
            for invoice_document in order.documents:
                result_data["customer_name"] = customer_name

                purchase_order = invoice_document.fields.get("PurchaseOrder")
                if purchase_order and hasattr(purchase_order, "value"):
                    purchase_order = re.sub("[^A-Za-z0-9]+", "", purchase_order.value)
                else:
                    invoice_id_field = invoice_document.fields.get("InvoiceId")
                    if invoice_id_field and hasattr(invoice_id_field, "value"):
                        purchase_order = invoice_id_field.value
                    else:
                        purchase_order = None

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
        
                print("shipping_address",result_data["shipping_address"])
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

                        if not product_code or product_code == "":
                            product_code, description = (
                                self.extract_part_number_and_description(description)
                            )

                        product_code = self.clean_product_code(product_code)
                        if not product_code:
                            continue
                        order_line_items.append(
                            {
                                "product_code": product_code,
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
                                "pdf_product_code": product_code,
                                
                            }
                        )
                print(order_line_items)
                result_data["order_line_items"] = product_mapper.find_best_match(
                    order_line_items
                )

            return result_data
        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )