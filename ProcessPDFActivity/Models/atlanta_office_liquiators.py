import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper

class AtlandaLiq:

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
        
    def extract_billing_address(self, result, tolerance=0.07):
        billing_data = {
            "address1": None,
            "address2": None,
            "city": None,
            "state": None,
            "zip_code": None,
        }

        # Updated reference polygons based on provided coordinates
        address_polygon = [(0.9025, 2.2964), (2.2683, 2.4301)]
        city_state_zip_polygon = [(0.893, 2.4444), (2.5166, 2.5829)]

        # Compute tolerance-based bounding box for address
        def get_bounds(polygon, tol):
            return {
                "min_x": min(p[0] for p in polygon) - tol,
                "max_x": max(p[0] for p in polygon) + tol,
                "min_y": min(p[1] for p in polygon) - tol,
                "max_y": max(p[1] for p in polygon) + tol,
            }

        address_bounds = get_bounds(address_polygon, tolerance)
        city_state_zip_bounds = get_bounds(city_state_zip_polygon, tolerance)

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
                    "min_x": min(p.x for p in item.polygon),
                    "max_x": max(p.x for p in item.polygon),
                    "min_y": min(p.y for p in item.polygon),
                    "max_y": max(p.y for p in item.polygon),
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
                            billing_data["zip_code"] = " ".join(
                                state_zip[1:]
                            ).strip()  # Handles ZIP+4

                # Break early if all data is found
                if all(billing_data.values()):
                    return [billing_data]

        return [billing_data]

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
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                result_data['shipping_address'][0]['addressee'] = invoice_document.fields.get("ShippingAddressRecipient").value.replace('\n'," ")
                result_data["billing_address"] = self.extract_billing_address(order)
               

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
                f"{customer_name} process data is failed. Reason: {str(ex)}"
            )
