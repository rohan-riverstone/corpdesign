import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
from pydantic import BaseModel, EmailStr, constr
from typing import Optional


class OfficeFurniture4Sale:
    
    def find_purchase_order(self, invoice_document):
        possible_keys = ["PurchaseOrder", "InvoiceId"]
        for key in possible_keys:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def extract_product_code(self, description):
        pattern = r"\[CD-[A-Za-z0-9-]+(?: \(Kit\)| \(Group\))?\]"

        # Search for the pattern in the text
        match = re.search(pattern, description)

        if match:
            part_number = match.group(0)  # Extract the matched text

            part_number = part_number.strip("[]")  # Remove square brackets
            pdf_part_number = part_number
            part_number = re.sub(
                r" \(Kit\)", "(Group)", part_number
            )  # Change "(Kit)" to "Kit"

            return part_number, pdf_part_number

        return None

    def extract_invoice_date(self, order, tolerance=0.05):

        # Define the bounding box with tolerance
        ref_bounds = {
            "min_x": 4.1247 - tolerance,
            "max_x": 5.7308 + tolerance,
            "min_y": 3.6945 - tolerance,
            "max_y": 4.0468 + tolerance,
        }

        extracted_date = None  # Store the extracted date

        for page in order.pages:
            for item in page.lines:
                if not item.polygon:
                    continue

                # Extract x and y values separately
                x_values = [
                    point[0] for point in item.polygon
                ]  # Extract all X coordinates
                y_values = [
                    point[1] for point in item.polygon
                ]  # Extract all Y coordinates

                # Compute bounding box of the item's polygon
                bounds = {
                    "min_x": min(x_values),
                    "max_x": max(x_values),
                    "min_y": min(y_values),
                    "max_y": max(y_values),
                }

                # Check if polygon is within reference bounds
                if (
                    ref_bounds["min_x"] <= bounds["min_x"] <= ref_bounds["max_x"]
                    and ref_bounds["min_x"] <= bounds["max_x"] <= ref_bounds["max_x"]
                    and ref_bounds["min_y"] <= bounds["min_y"] <= ref_bounds["max_y"]
                    and ref_bounds["min_y"] <= bounds["max_y"] <= ref_bounds["max_y"]
                ):

                    match = re.search(r"\d{2}/\d{2}/\d{4}", item.content)
                    if match:
                        extracted_date = match.group()

        return extracted_date

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
                else:
                    result_data["invoice_date"] = self.extract_invoice_date(order)

                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                result_data['shipping_address'][0]['addressee'] = invoice_document.fields.get("ShippingAddressRecipient").value.replace('\n'," ")

                vendor_address = invoice_document.fields.get("CustomerAddress")
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
                        description = (
                            item.value.get("Description").value.replace("\n", "")
                            if item.value.get("Description")
                            else ""
                        )
                        if product_code:
                            adjusted_product_code = self.adjust_product_code(
                                product_code
                            )
                        else:
                            print(description)
                            adjusted_product_code, pdf_part_number = (
                                self.extract_product_code(description)
                            )

                        result_data["order_line_items"].append(
                            {
                                "product_code": adjusted_product_code,
                                "description": description,
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
                                "pdf_product_code": pdf_part_number,
                                
                            }
                        )
            result_data["order_line_items"] = product_mapper.find_best_match(
                result_data["order_line_items"]
            )
            return result_data
        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )
