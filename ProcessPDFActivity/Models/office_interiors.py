import re
import logging
from ...system.Utilities import Utility


class OfficeInt:
    def adjust_product_code(self, product_code: str) -> str:
        if re.match(r"CD-\d{3,}[A-Z]$", product_code):
            return product_code + "S (2)"

    def find_purchase_order(self, invoice_document):
        possible_keys = ["PurchaseOrder", "InvoiceId"]
        for key in possible_keys:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def process_data(self, data, customer_name):
        try:
            order = data.result()
            result_data = {}
            result_data["customer_name"] = customer_name

            for invoice_document in order.documents:
                result_data["purchase_order"] = self.find_purchase_order(
                    invoice_document
                )

                invoice_date = invoice_document.fields.get("InvoiceDate")
                if invoice_date and invoice_date.value:
                    result_data["invoice_date"] = invoice_date.value.strftime(
                        "%m/%d/%Y"
                    )

                billing_address = invoice_document.fields.get("ShippingAddress")
                if billing_address and billing_address.value:
                    result_data["shipping_address"] = Utility.splitted_address(
                        billing_address.value.to_dict()
                    )

                vendor_address = invoice_document.fields.get("VendorAddress")
                if vendor_address and vendor_address.value:
                    result_data["billing_address"] = Utility.splitted_address(
                        vendor_address.value.to_dict()
                    )

                result_data["order_line_items"] = []

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
                        adjusted_product_code = self.adjust_product_code(product_code)

                        result_data["order_line_items"].append(
                            {
                                "product_code": adjusted_product_code,
                                "description": (
                                    item.value.get("Description").value.replace(
                                        "\n", ""
                                    )
                                    if item.value.get("Description")
                                    else ""
                                ),
                                "qty": (
                                    item.value.get("Quantity").value
                                    if item.value.get("Quantity")
                                    else 0
                                ),
                                "unit_price": (
                                    item.value.get("UnitPrice").value.amount
                                    if item.value.get("UnitPrice")
                                    else 0.0
                                ),
                                "amount": (
                                    item.value.get("Amount").value.amount
                                    if item.value.get("Amount")
                                    else 0.0
                                ),
                                "pdf_product_code": adjusted_product_code,
                            }
                        )

            return result_data
        except Exception as ex:
            logging.error(f"Office interiors process data is failed. Reason: {str(ex)}")
