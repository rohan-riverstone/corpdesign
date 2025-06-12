import logging
import re
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper


class DallasDesk:
    PRODUCT_CODE_REGEX = re.compile(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b(?:\s*\(GROUP\))?")

    INVOICE_DATE_POLYGON = [
        (5.3111, 0.975),
        (5.7165, 0.9735),
        (5.7165, 1.0795),
        (5.3105, 1.0795),
    ]
    BILLING_ADDRESS_POLYGON = [(0.5301, 2.1819), (1.4087, 2.2917)]
    BILLING_CITY_STATE_ZIP_POLYGON = [(0.5253, 2.3776), (1.3037, 2.4874)]
    SHIPPING_CITY_STATE_ZIP_POLYGON = [
        (0.5157, 4.3542),
        (1.466, 4.3589),
        (1.466, 4.4735),
        (0.5157, 4.4688),
    ]
    SHIPPING_ADDRESSEE_POLYGON = [
        (0.5253, 3.8529),
        (1.8958, 3.8529),
        (1.8958, 3.9722),
        (0.5253, 3.9674),
    ]
    
    SHIPPING_PHONE_POLYGON = [
        (1.1031, 4.526),
        (1.7478, 4.526),
        (1.7478, 4.6359),
        (1.1031, 4.6359),
    ]


    def _is_within_bounds(self, line, ref_polygon, tolerance=0.05):
        """Check if a line's position matches a reference area with tolerance."""
        if not line.polygon:
            return False

        line_min_x = min(p[0] for p in line.polygon)
        line_max_x = max(p[0] for p in line.polygon)
        line_min_y = min(p[1] for p in line.polygon)
        line_max_y = max(p[1] for p in line.polygon)

        ref_min_x = min(p[0] for p in ref_polygon) - tolerance
        ref_max_x = max(p[0] for p in ref_polygon) + tolerance
        ref_min_y = min(p[1] for p in ref_polygon) - tolerance
        ref_max_y = max(p[1] for p in ref_polygon) + tolerance

        return (
            ref_min_x <= line_min_x <= ref_max_x
            and ref_min_x <= line_max_x <= ref_max_x
            and ref_min_y <= line_min_y <= ref_max_y
            and ref_min_y <= line_max_y <= ref_max_y
        )

    def _extract_invoice_info(self, order):
        """Single-pass extraction of key invoice information."""
        info = {
            "invoice_date": None,
            "billing_address": {
                "address1": None,
                "address2": "",
                "city": None,
                "state": None,
                "zip_code": None,
            },
            "shipping_info": {
                "addressee": None,
                "address1":None,                
                "city": None,
                "state": None,
                "zip_code": None,
            },
        }

        for page in order.pages:
            for line in page.lines:
                content = line.content.strip()

                if self._is_within_bounds(line, self.INVOICE_DATE_POLYGON):
                    info["invoice_date"] = content.replace("-", "")

                elif self._is_within_bounds(line, self.BILLING_ADDRESS_POLYGON):
                    info["billing_address"]["address1"] = content

                elif self._is_within_bounds(line, self.BILLING_CITY_STATE_ZIP_POLYGON):
                    parts = content.split(", ")
                    if len(parts) >= 2:
                        info["billing_address"]["city"] = parts[0].strip()
                        state_zip = parts[1].split()
                        if len(state_zip) >= 2:
                            (
                                info["billing_address"]["state"],
                                info["billing_address"]["zip_code"],
                            ) = (state_zip[0].strip(), state_zip[1].strip())

                elif self._is_within_bounds(line, self.SHIPPING_ADDRESSEE_POLYGON):
                    info["shipping_info"]["addressee"] = content

                elif self._is_within_bounds(line, self.SHIPPING_CITY_STATE_ZIP_POLYGON):
                    parts = content.split(", ")
                    if len(parts) >= 2:
                        info["shipping_info"]["city"] = parts[0].strip()
                        state_zip = parts[1].split()
                        if len(state_zip) >= 2:
                            (
                                info["shipping_info"]["state"],
                                info["shipping_info"]["zip_code"],
                            ) = (state_zip[0].strip(), state_zip[1].strip())

                elif self._is_within_bounds(line, self.SHIPPING_PHONE_POLYGON):
                    if info["shipping_info"]['addressee'] is not None:
                        info["shipping_info"]["address1"] =content

        return info

    def _extract_product_data(self, table):
        """Efficient extraction of product data from table structures."""
        extracted = []
        rows = {}

        for cell in table.cells:
            if cell.row_index not in rows:
                rows[cell.row_index] = {}
            rows[cell.row_index][cell.column_index] = cell.content.strip()

        sorted_rows = sorted(rows.items())
        for idx, (row_idx, row) in enumerate(sorted_rows):
            if len(row) < 5 or row.get(2):
                continue  # Skip headers and invalid rows

            product_code, addition_description = self._parse_product_code(
                row.get(1, "")
            )
            qty = row.get(3, "0")
            if not qty.isdigit():
                continue

            next_row = sorted_rows[idx + 1][1] if idx + 1 < len(sorted_rows) else {}
            desc = next_row.get(1, "").replace("\n", " ").strip()
            if addition_description != "" and addition_description:
                desc = addition_description + " " + desc
            unit_price = next_row.get(3, "0").replace(",", "")
            amount = next_row.get(4, "0").replace(",", "")

            try:
                extracted.append(
                    {
                        "product_code": product_code,
                        "description": desc.replace(product_code, ""),
                        "qty": int(qty),
                        "unit_price": float(unit_price),
                        "amount": float(amount),
                        "pdf_product_code": product_code,
                        
                    }
                )
            except ValueError:
                continue

        return extracted

    def _parse_product_code(self, data):
        """Extract product code using precompiled regex."""
        cleaned = data.replace("*", "").strip()
        match = self.PRODUCT_CODE_REGEX.search(cleaned)
        if match:
            return match.group().strip(), cleaned[match.end() :].strip()
        return "", None

    def process_data(self, data, customer_name):
        """Main processing method with optimized data flow."""
        try:
            order = data.result()
            result = {
                "customer_name": customer_name,
                "purchase_order": "",
                "invoice_date": None,
                "shipping_address": [],
                "billing_address": [],
                "order_line_items": [],
            }

            invoice_info = self._extract_invoice_info(order)
            result["invoice_date"] = invoice_info["invoice_date"]
            result["billing_address"] = [invoice_info["billing_address"]]

            for doc in order.documents:
                result["purchase_order"] = self._get_purchase_order(doc)
                shipping_address = doc.fields.get("ShippingAddress")

                if shipping_address and shipping_address.value:
                    processed = Utility.splitted_address(
                        shipping_address.value.to_dict(),flag=True
                    )
                    for key, value in invoice_info["shipping_info"].items():
                        if processed[0].get(key) in ["None", None, ""]:
                            processed[0][key] = value  

                    result["shipping_address"] = processed

            result["order_line_items"] = product_mapper.find_best_match(
                [
                    item
                    for table in order.tables
                    for item in self._extract_product_data(table)
                ]
            )

            return result

        except Exception as e:
            logging.error(f"Processing failed: {str(e)}", exc_info=True)
            return {}

    def _get_purchase_order(self, document):
        """Extract purchase order number from document fields."""
        for key in ["PurchaseOrder", "InvoiceId"]:
            field = document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^\w]", "", field.value)
        return ""
