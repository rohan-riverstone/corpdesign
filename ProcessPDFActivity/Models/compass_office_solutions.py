import re
import logging
from ..BL.part_number_map import product_mapper
from ...system.Utilities import Utility
class CompassOfficeSolution:

    def find_purchase_order(self, invoice_document):
        possible_keys = ["PurchaseOrder", "InvoiceId"]
        for key in possible_keys:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def extract_product_code_and_description(self, text):
        cleaned_text = text.replace(' --- ', '-').replace(' -- ', '-').strip()
        print(cleaned_text)

        pattern_cd = r"\b(CD[-_][\w-]+)\s*[-\s]*\s*(.*)"
        pattern_be = r"\b(BE[0-9-]+)\b\s*(.*)"

        match = re.match(pattern_cd, cleaned_text)
        if not match:
            match = re.match(pattern_be, cleaned_text)

        if match:
            product_code = match.group(1)
            description = match.group(2).strip()  
            return product_code.replace('--','-'), description if description else None  

        return None, None

    def process_data(self, data, customer_name):
        try:
            order = data.result()
            result_data = {
                "customer_name": customer_name,
                "order_line_items": [],
            }

            for invoice_document in order.documents:
                result_data["purchase_order"] = self.find_purchase_order(invoice_document)

                invoice_date = invoice_document.fields.get("InvoiceDate")
                if invoice_date and invoice_date.value and hasattr(invoice_date.value, "strftime"):
                    result_data["invoice_date"] = invoice_date.value.strftime("%m/%d/%Y")

                # Handling shipping address
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address and shipping_address.value:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict()
                    )

                # Handling billing address
                billing_address = invoice_document.fields.get("CustomerAddress")
                if billing_address and billing_address.value:
                    result_data["billing_address"] = Utility.splitted_address(
                        billing_address.value.to_dict()
                    )

                items = invoice_document.fields.get("Items")
                if items and items.value:
                    for item in items.value:
                        description_field = item.value.get("Description")
                        description = description_field.value.replace("\n", " ") if description_field else ""

                        product_code, description = self.extract_product_code_and_description(description) or ("", "")

                        result_data["order_line_items"].append(
                            {
                                "product_code": product_code,
                                "description": description,
                                "qty": item.value.get("Quantity").value if item.value.get("Quantity") else 0,
                                "unit_price": item.value.get("UnitPrice").value.amount if item.value.get("UnitPrice") else 0.0,
                                "amount": item.value.get("Amount").value.amount if item.value.get("Amount") else 0.0,
                                "pdf_product_code": product_code,
                            }
                        )
                result_data['order_line_items']=product_mapper.find_best_match(result_data['order_line_items'])
            return result_data
        except Exception as ex:
            logging.error(f"Atlantda office liquidator process data failed. Reason: {str(ex)}")
            return None
