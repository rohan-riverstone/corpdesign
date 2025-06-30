import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper

class TurnkeyProjectServices:

    def process_data(self, data, customer_name, address_tolerance=0.05, phone_tolerance=0.5):
        try:
            order = data.result()
            result_data = {
                "customer_name": customer_name,
            }

            # Reference bounds for billing address extraction (tune as needed)
            ref_bounds_address = {
                "min_x": 0.30 - address_tolerance,
                "max_x": 2.05 + address_tolerance,
                "min_y": 1.78 - address_tolerance,
                "max_y": 2.21 + address_tolerance,
            }

            ref_bounds_phone = {
                "min_x": 0.3104 - phone_tolerance,
                "max_x": 1.6475 + phone_tolerance,
                "min_y": 0.74 - phone_tolerance,
                "max_y": 0.9023 + phone_tolerance,
            }

            address_lines = []
            zip_code = None
            zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")
            phone_pattern=re.compile(r"\(\d{3}\)\s\d{3}-\d{4}")

            # Loop through pages and lines to extract billing address lines
            for page in order.pages:
                for item in page.lines:
                    if not item.polygon:
                        continue

                    bounds = {
                        "min_x": min(p.x for p in item.polygon),
                        "max_x": max(p.x for p in item.polygon),
                        "min_y": min(p.y for p in item.polygon),
                        "max_y": max(p.y for p in item.polygon),
                    }

                    # Check if line is within the reference bounds for billing address
                    in_bounds = (
                        ref_bounds_address["min_x"] <= bounds["min_x"] <= ref_bounds_address["max_x"]
                        and ref_bounds_address["min_x"] <= bounds["max_x"] <= ref_bounds_address["max_x"]
                        and ref_bounds_address["min_y"] <= bounds["min_y"] <= ref_bounds_address["max_y"]
                        and ref_bounds_address["min_y"] <= bounds["max_y"] <= ref_bounds_address["max_y"]
                    )

                    if in_bounds:
                        line_text = item.content.strip().replace("-", "")
                        address_lines.append(line_text)

                        # Extract zip code if present
                        zip_match = zip_pattern.search(item.content)
                        if zip_match:
                            zip_code = zip_match.group()

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
                            print(primary_phone_number)


            # Extract shipping address from invoice document fields
            for invoice_document in order.documents:
                shipping_address = invoice_document.fields.get("ShippingAddress")
                if shipping_address:
                    # Use utility to split address into components
                    result_data["shipping_address"] = Utility.splitted_address(
                        shipping_address.value.to_dict(), flag=True
                    )[0]
                    recipient = invoice_document.fields.get("ShippingAddressRecipient")
                    if recipient:
                        # Add recipient as addressee and adjust address fields
                        result_data['shipping_address']['addressee'] = recipient.value.replace('\n', " ")+ f", {primary_phone_number}"          

            # Extract billing address if enough lines and zip code found
            if len(address_lines) >= 3 and zip_code:
                result_data["billing_address"] = {
                    "address1": address_lines[0],
                    "address2": address_lines[1],
                    "city": address_lines[2].split(',')[0].strip(),
                    "state": address_lines[2].split(',')[1].strip().split(" ")[0],
                    "zip_code": zip_code
                }

            # Extract and format invoice date
            date_value = order.documents[0].fields['InvoiceDate'].value
            result_data['invoice_date'] = date_value.strftime("%m/%d/%Y")

            # Extract purchase order number
            result_data['purchase_order'] = order.documents[0].fields['PurchaseOrder'].value

            # Extract order line items from table
            result_data["order_line_items"] = self.extract_from_table(order)
            result_data["order_line_items"]=product_mapper.find_best_match(result_data["order_line_items"])

            # Print or log the result for debugging
            print(f"result_data: {result_data}")
            return result_data

        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}",exc_info=True
            )

    # Extract data from the table.
    def extract_from_table(self, data):
        order_line_items = []
        for table in data.tables:
            if table.column_count == 7:
                rows = {}
                for cell in table.cells:
                    if cell.kind == "columnHeader":
                        continue
                    row_idx = cell.row_index
                    col_idx = cell.column_index
                    # Clean up cell content
                    content = cell.content.replace("\n", " ").strip()
                    if row_idx not in rows:
                        rows[row_idx] = {}
                    rows[row_idx][col_idx] = content
                sorted_row_indices = sorted(rows.keys())

                for idx, row_idx in enumerate(sorted_row_indices):
                    row = [rows[row_idx].get(col_idx, "") for col_idx in range(7)]
                    # Skip empty rows
                    if not row or all(cell.strip() == "" for cell in row):
                        continue

                    # Map row data to item dictionary
                    item = {
                        "Line": row[0],
                        "product_code": row[1].strip(),
                        "description": row[2].replace("\n", " "),
                        "qty": float(row[3]),
                        "unit_price": float(re.sub(r'[^\d.]', '', row[5])),
                        "amount": float(re.sub(r'[^\d.]', '', row[6])),
                        "pdf_product_code": row[1].strip()
                    }
                    order_line_items.append(item)
        return order_line_items