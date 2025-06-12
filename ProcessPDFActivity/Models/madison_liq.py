import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper


class MadisonLiq:    

    def extract_data_from_poly(self, order, address_tolerance=0.05, phone_tolerance=0.5):
        ref_bounds_address = {
            "min_x": 0.4191 - address_tolerance,
            "max_x": 1.7431 + address_tolerance,
            "min_y": 1.6106 - address_tolerance,
            "max_y": 2.0358 + address_tolerance,
        }

        ref_bounds_phone = {
            "min_x": 2.8 - phone_tolerance,
            "max_x": 3.5 + phone_tolerance,
            "min_y": 2.2 - phone_tolerance,
            "max_y": 2.7 + phone_tolerance,
        }

        phone_pattern = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
        zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")  # Matches 5-digit ZIPs and ZIP+4

        address_lines = []
        primary_phone_number = None  
        secondary_phone_number = None  
        zip_code = None

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

                # Extract address
                if (
                    ref_bounds_address["min_x"] <= bounds["min_x"] <= ref_bounds_address["max_x"]
                    and ref_bounds_address["min_x"] <= bounds["max_x"] <= ref_bounds_address["max_x"]
                    and ref_bounds_address["min_y"] <= bounds["min_y"] <= ref_bounds_address["max_y"]
                    and ref_bounds_address["min_y"] <= bounds["max_y"] <= ref_bounds_address["max_y"]
                ):
                    address_lines.append(item.content.strip().replace("-", ""))

                # Extract phone number
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
                    
                    if not primary_phone_number and not secondary_phone_number:
                        secondary_phone_number = found_phone

                # Extract ZIP code
                zip_match = zip_pattern.search(item.content)
                if zip_match:
                    if (
                        ref_bounds_phone["min_x"] <= bounds["min_x"] <= ref_bounds_phone["max_x"]
                        and ref_bounds_phone["min_x"] <= bounds["max_x"] <= ref_bounds_phone["max_x"]
                        and ref_bounds_phone["min_y"] <= bounds["min_y"] <= ref_bounds_phone["max_y"]
                        and ref_bounds_phone["min_y"] <= bounds["max_y"] <= ref_bounds_phone["max_y"]
                    ):
                        zip_code = zip_match.group().strip()

        phone_number = primary_phone_number or secondary_phone_number
        if not phone_number:
            phone_number = ""

        if not zip_code:
            zip_code = ""

        return {"address_lines": address_lines, "phone_number": phone_number, "zip_code": zip_code}


    

    def extract_clean_product_code(self, text):
        text = text.replace("\n", " ")

        text = re.sub(r"(Corp|Design|:|\s+)", "", text, flags=re.IGNORECASE)

        match = re.search(r"(CD-[A-Za-z0-9-]+)", text)

        return match.group(1) if match else ""

    def find_purchase_order(self, invoice_document):
        possible_keys = ["PurchaseOrder", "InvoiceId"]
        for key in possible_keys:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def extract_data_from_table(self, order):
        extracted_items = []

        for table in order.tables:
            rows = {}

            for cell in table.cells:
                if cell.row_index not in rows:
                    rows[cell.row_index] = {}
                rows[cell.row_index][cell.column_index] = cell.content.strip()

            number_pattern = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$")

            for row_index in sorted(rows.keys()):
                product_code = rows[row_index].get(0, "")
                if (
                    product_code is None
                    or product_code.lower().strip() == "services:shipcd"
                    or "services" in product_code.lower()
                    or "CD" not in product_code
                ):
                    continue
                elif product_code.lower().strip() == "corp" and (row_index + 1) in rows:
                    product_code += rows[row_index + 1].get(0, "")

                description = rows[row_index].get(1, "")
                if description is None:
                    continue

                qty = rows[row_index].get(2, "0").strip()
                unit_price = rows[row_index].get(3, "0.0").strip()
                amount = rows[row_index].get(4, "0.0").strip()

                qty = int(qty) if qty.isdigit() else 0

                unit_price = (
                    float(unit_price.replace(",", ""))
                    if number_pattern.match(unit_price)
                    else 0.0
                )
                amount = (
                    float(amount.replace(",", ""))
                    if number_pattern.match(amount)
                    else 0.0
                )

                if qty == 0 and amount == 0.0 and unit_price == 0.0:
                    continue
                product_code = self.extract_clean_product_code(product_code)
                #  extraction from excel
                extracted_items.append(
                    {
                        "product_code": product_code,
                        "description": description,
                        "qty": qty,
                        "unit_price": unit_price,
                        "amount": amount,
                        "pdf_product_code": product_code,
                        
                    }
                )

        return extracted_items

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

                shiping_address = invoice_document.fields.get("ShippingAddress")
                if shiping_address and shiping_address.value:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shiping_address.value.to_dict(),flag=True
                    )

                if (
                    isinstance(result_data["shipping_address"], list)
                    and result_data["shipping_address"]
                ):
                    if not result_data["shipping_address"][0].get("city"):
                        address = shiping_address.value.to_dict()
                        result_data["shipping_address"][0]["city"] = address.get(
                            "city_district", ""
                        )
                extracted_data=self.extract_data_from_poly(order)                        

                data = invoice_document.fields.get("ShippingAddressRecipient").value.split('\n')
                addressee = data[1] if len(data) > 1 else ""
                address1 = data[0]  +", "+ extracted_data['phone_number']
                if result_data['shipping_address'][0]['zip_code'] == 'None':
                    result_data['shipping_address'][0]['zip_code'] = extracted_data['zip_code']
                result_data['shipping_address'][0]['addressee'] = addressee
                result_data['shipping_address'][0]['address1'] = address1
                vendor_address = extracted_data['address_lines']
                if vendor_address and len(vendor_address) >= 2:
                    address = vendor_address[1]
                    city_state_zip = (
                        vendor_address[2] if len(vendor_address) > 2 else ""
                    )

                    city, state, zip_code = "", "", ""
                    if city_state_zip:
                        parts = city_state_zip.split(",")
                        city = parts[0].strip() if len(parts) > 0 else ""
                        state_zip = parts[1].strip() if len(parts) > 1 else ""

                        state_zip_split = re.split(r"\s+", state_zip)
                        state = state_zip_split[0] if len(state_zip_split) > 0 else ""
                        zip_code = (
                            state_zip_split[-1]
                            if len(state_zip_split) > 1
                            and state_zip_split[-1].isdigit()
                            else ""
                        )

                    result = {
                        "address1": (
                            vendor_address[0] if len(vendor_address) > 0 else ""
                        ),
                        "address2": address,
                        "city": city,
                        "state": state,
                        "zip_code": zip_code,
                    }
                result_data["billing_address"] = result

            result_data["order_line_items"] = self.extract_data_from_table(order=order)
            result_data["order_line_items"] = product_mapper.find_best_match(
                result_data["order_line_items"]
            )
            print(result_data)
            return result_data
        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )
