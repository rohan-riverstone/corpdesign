import re
import logging
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper
import json

class CommercialDesignServices:
    def extract_data_from_table(self, result):
        """
        Extracts order line items from the analyze_result object.
        Skips the first two rows and the last row of each table.
        """
        order_line_items = []
        for table in result.tables:
            if table.column_count == 5:
                rows = {}
                for cell in table.cells:
                    if hasattr(cell, "kind") and cell.kind == "columnHeader":
                        continue
                    row_idx = cell.row_index
                    col_idx = cell.column_index
                    # Clean up cell content
                    content = cell.content
                    if row_idx not in rows:
                        rows[row_idx] = {}
                    rows[row_idx][col_idx] = content

                sorted_row_indices = sorted(rows.keys())

                # Skip the first two rows and leave the last row
                for idx, row_idx in enumerate(sorted_row_indices[2:-1]):
                    row = [rows[row_idx].get(col_idx, "") for col_idx in range(5)]
                    if not row or all(cell.strip() == "" for cell in row):
                        continue
                    split_description = row[2].split("\n")
                    if len(split_description) > 1:
                        row[2] = " ".join(split_description[:2])
                    match = re.search(r'\b\d+\b', row[1])
                    item = {
                        "Line": row[0],
                        "qty": int(match.group()) if match else 0,
                        "product_code": self.extract_clean_product_code(split_description[0].strip()),
                        "description": split_description[1].strip(),
                        "unit_price": float(row[3]) if row[3] else 0.0,
                        "amount": float(row[4].replace(',', '')) if row[4] else 0.0,
                        "pdf_product_code": self.extract_clean_product_code(split_description[0].strip())
                    }
                    order_line_items.append(item)
        return order_line_items

    def extract_clean_product_code(self, code):
        code= code.replace(" -- ", "-")
        code=code.replace(" --- ", "-")
        return code

    def process_data(self, data, customer_name, address_tolerance=0.05, phone_tolerance=0.5):
        """
        Main processing function for Commercial Design Services.
        Extracts addresses, invoice date, purchase order, and order line items.
        """
        try:
            # If data is a poller, get the result
            if hasattr(data, "result"):
                order = data.result()
            else:
                order = data

            result_data = {
                "customer_name": customer_name
            }

            # Reference bounds for billing address extraction
            ref_bounds_address = {
                "min_x": 0.75 - address_tolerance,
                "max_x": 2.3 + address_tolerance,
                "min_y": 2.4 - address_tolerance,
                "max_y": 2.85 + address_tolerance,
            }

            # Reference bounds for phone number extraction
            ref_bounds_phone = {
                "min_x": 2.55 - phone_tolerance,
                "max_x": 3.2472 + phone_tolerance,
                "min_y": 1.0026 - phone_tolerance,
                "max_y": 1.1267 + phone_tolerance,
            }

            address_lines = []
            zip_code = None
            zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")
            phone_pattern = re.compile(r"\d{3}[-.\s]\d{3}[-.\s]\d{4}")
            primary_phone_number = None

            # Extract billing address and phone number from page lines
            for page in order.pages:
                for item in page.lines:
                    if not hasattr(item, "polygon") or not item.polygon:
                        continue

                    bounds = {
                        "min_x": min(p.x for p in item.polygon),
                        "max_x": max(p.x for p in item.polygon),
                        "min_y": min(p.y for p in item.polygon),
                        "max_y": max(p.y for p in item.polygon),
                    }

                    # Check if the line is within the billing address bounds
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

                    # Extract phone number if present and within bounds
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

            # Extract shipping address and add recipient/phone if available
            if hasattr(order, "documents"):
                for invoice_document in order.documents:
                    shipping_address = invoice_document.fields.get("ShippingAddress")
                    if shipping_address:
                        result_data["shipping_address"] = Utility.splitted_address(
                            shipping_address.value.to_dict(), flag=True
                        )[0]
                        recipient = invoice_document.fields.get("ShippingAddressRecipient")
                        if recipient and primary_phone_number:
                            # Add recipient and phone number to addressee
                            result_data['shipping_address']['addressee'] = (
                                recipient.value.replace('\n', " ") + f', {primary_phone_number}'
                            )

            # Build billing address dictionary
            if len(address_lines) >= 3 and zip_code:
                result_data["billing_address"] = {
                    "address1": address_lines[0],
                    "address2": address_lines[1],
                    "city": address_lines[2].split(',')[0].strip(),
                    "state": address_lines[2].split(',')[1].strip().split(" ")[0] if ',' in address_lines[2] else "",
                    "zip_code": zip_code
                }

            # Extract invoice date from lines using regex
            match = None
            if hasattr(order, "pages"):
                for page in order.pages:
                    lines = page.lines
                    for items in lines:
                        date_pattern = re.compile(r"\b(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])/(\d{4})\b")
                        match = date_pattern.search(items.content)
                        if match:
                            break
            result_data["invoice_date"] = match.group() if match else None

            # Extract purchase order number from table if available
            tables = getattr(order, "tables", None)
            if tables and hasattr(tables[0], "cells") and len(tables[0].cells) > 1:
                po = tables[0].cells
                po_num = po[1].content.replace("\n", " ").strip()
                result_data["purchase_order"] = po_num
            else:
                result_data["purchase_order"] = None

            # Extract and map order line items
            result_data["order_line_items"] = self.extract_data_from_table(order)
            result_data["order_line_items"] = product_mapper.find_best_match(result_data["order_line_items"])

            return result_data

        except Exception as ex:
            logging.error(
                f"{customer_name} process data is failed. Reason: {str(ex)}", exc_info=True
            )