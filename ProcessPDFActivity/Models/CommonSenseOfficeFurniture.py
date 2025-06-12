import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import copy
from pydantic import BaseModel, EmailStr, constr
from typing import Optional

class CommonSenseOfficeFurniture:
    def find_purchase_order(self, invoice_document):
        possible_keys = ["PurchaseOrder", "InvoiceId"]
        for key in possible_keys:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def extract_product_code_from_table(self, description, order):

        for table in order.tables:

            rows = {}
            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = {}
                rows[cell.row_index][cell.column_index] = cell.content

            for row_index in sorted(rows.keys()):
                row_desc = rows[row_index].get(1, None)
                row_code = rows[row_index].get(0, None)

                if row_desc and row_code and description.lower() in row_desc.lower():
                    return row_code, description

        return ""
    def extract_shipping_address(self, order, tolerance=0.05):
        ref_bounds = {
            "min_x": 5.4072,  # 5.4572 - 0.05
            "max_x": 7.5556,  # 7.5056 + 0.05
            "min_y": 2.048,   # 2.098 - 0.05
            "max_y": 3.1348,  # 3.0848 + 0.05
        }

        address_lines = []

        for page in order.pages:
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
                    address_lines.append(item.content.strip().replace("-", ""))  

        if len(address_lines) < 3:
            return {"error": "Insufficient address data", "raw_output": address_lines}

        data_text = " ".join(address_lines)  

        EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        PHONE_PATTERN = r"\b\d{10,}\b"
        ZIP_PATTERN = r"\b\d{5}\b"

        email_match = re.search(EMAIL_PATTERN, data_text)
        phone_match = re.search(PHONE_PATTERN, data_text)
        zip_match = re.search(ZIP_PATTERN, data_text)

        class CustomerDetails(BaseModel):
            customer_name: str
            company_name: str
            street_address: str
            city: str
            state: str
            zip_code: Optional[constr(min_length=5, max_length=10)] = None # type: ignore
            phone_number: Optional[constr(min_length=10, max_length=15)] = None # type: ignore
            email: Optional[EmailStr] = None

        company_name = address_lines[1] if len(address_lines) > 1 else ""
        street_address = address_lines[2] if len(address_lines) > 2 else ""
        city_state_zip = address_lines[3] if len(address_lines) > 3 else ""

        city, state, zip_code = "", "", None

        city_state_zip_parts = city_state_zip.split(", ")
        if len(city_state_zip_parts) == 2:
            city = city_state_zip_parts[0]
            state_zip = city_state_zip_parts[1].split(" ")
            if len(state_zip) == 2:
                state, zip_code = state_zip
            elif len(state_zip) == 1:
                state = state_zip[0]

        customer_details = CustomerDetails(
            customer_name="",  # Not available in the input data
            company_name=company_name,
            street_address=street_address,
            city=city,
            state=state,
            zip_code=zip_code if zip_code and re.match(ZIP_PATTERN, zip_code) else None,
            phone_number=phone_match.group(0) if phone_match else None,
            email=email_match.group(0) if email_match else None
        )

        shipping_address = {
            "addressee": customer_details.company_name,
            "address1": customer_details.customer_name + (" " + customer_details.phone_number if customer_details.phone_number else ""),
            "address2": customer_details.street_address,
            "city": customer_details.city,
            "state": customer_details.state,
            "zip_code": customer_details.zip_code,
        }

        return [shipping_address]
    
    def extract_billing_address(self, result, tolerance=0.07):
        billing_data = {
            "address1": None,
            "address2": None,
            "city": None,
            "state": None,
            "zip_code": None,
            "phone_number": None,  # Added phone number field
        }

        # Compute tolerance-based bounding box
        def get_bounds(polygon, tol):
            return {
                "min_x": min(p[0] for p in polygon) - tol,
                "max_x": max(p[0] for p in polygon) + tol,
                "min_y": min(p[1] for p in polygon) - tol,
                "max_y": max(p[1] for p in polygon) + tol,
            }

        address_bounds = get_bounds([(0.4759, 1.9384), (1.512, 2.0626)], tolerance)
        city_state_zip_bounds = get_bounds([(0.4793, 2.0869), (1.5153, 2.2069)], tolerance)
        phone_bounds = get_bounds([(0.4756, 2.2408), (1.427, 2.3578)], tolerance)

        def is_within_bounds(bounds, item_bounds):
            return (
                bounds["min_x"] <= item_bounds["min_x"] <= bounds["max_x"]
                and bounds["min_x"] <= item_bounds["max_x"] <= bounds["max_x"]
                and bounds["min_y"] <= item_bounds["min_y"] <= bounds["max_y"]
                and bounds["min_y"] <= item_bounds["max_y"] <= bounds["max_y"]
            )

        # Iterate over document pages
        for page in result.pages:
            for item in page.lines:
                if not item.polygon:
                    continue

                # Get current text bounding box
                item_bounds = {
                    "min_x": min(p[0] for p in item.polygon),
                    "max_x": max(p[0] for p in item.polygon),
                    "min_y": min(p[1] for p in item.polygon),
                    "max_y": max(p[1] for p in item.polygon),
                }

                text_content = item.content.strip()

                # Check if this is the address line
                if is_within_bounds(address_bounds, item_bounds):
                    billing_data["address1"] = text_content

                # Check if this is the city, state, and zip code line
                elif is_within_bounds(city_state_zip_bounds, item_bounds):
                    parts = text_content.split(", ")
                    if len(parts) == 2:
                        city = parts[0].strip()
                        state_zip = parts[1].split(" ")

                        if len(state_zip) >= 2:
                            billing_data["city"] = city
                            billing_data["state"] = state_zip[0].strip()
                            billing_data["zip_code"] = " ".join(state_zip[1:]).strip()

                # Check if this is the phone number line
                elif is_within_bounds(phone_bounds, item_bounds):
                    billing_data["phone_number"] = text_content.replace("Phone: ", "").strip()

                # Break early if all data is found
                if all(billing_data.values()):
                    return [billing_data]

        return [billing_data]


    def process_data(self, data, customer_name):
        print("it enters here")

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

                result_data["shipping_address"] = self.extract_shipping_address(order)
                result_data["billing_address"] = self.extract_billing_address(order)
                print("shipping_address",result_data["shipping_address"])
                print("asdsadsadsa")

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
                            item.value.get("Description").value
                            if item.value.get("Description")
                            else ""
                        )
                        
                        if product_code == "" or product_code is None:
                            #  extraction from excel
                            product_code, description = (
                                self.extract_product_code_from_table(description, order)
                            )

                        result_data["order_line_items"].append(
                            {
                                "product_code": product_code,
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
                                "pdf_product_code": product_code,
                            }
                        )
            result_data["order_line_items"] = product_mapper.find_best_match(
                result_data["order_line_items"]
            )
            return result_data
        except Exception as ex:
            logging.error(
                f"COMMONSENSE OFFICE FURNITURE process data is failed. Reason: {str(ex)}"
            )