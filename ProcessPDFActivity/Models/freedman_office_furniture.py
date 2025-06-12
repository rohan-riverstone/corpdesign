import re
import logging
from rapidfuzz import fuzz
from ...system.Utilities import Utility
from ..BL.part_number_map import product_mapper


class FreedmanOfficeFurniture:

    def adjust_product_code(self, product_code):
        product_rules = {}
        return product_rules.get(product_code, product_code)

    def find_purchase_order(self, invoice_document):
        for key in {"PurchaseOrder", "InvoiceId"}:
            field = invoice_document.fields.get(key)
            if field and field.value:
                return re.sub(r"[^A-Za-z0-9]+", "", field.value)
        return ""

    def extract_purchase_order_number(self, result, tolerance=0.05):
        reference_polygon = [
            (5.6539, 0.7543),
            (6.8239, 0.7496),
            (6.8239, 0.8785),
            (5.6539, 0.8832),
        ]
        ref_bounds = {
            "min_x": min(p[0] for p in reference_polygon) - tolerance,
            "max_x": max(p[0] for p in reference_polygon) + tolerance,
            "min_y": min(p[1] for p in reference_polygon) - tolerance,
            "max_y": max(p[1] for p in reference_polygon) + tolerance,
        }

        for page in result.pages:
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
                    return item.content.strip().replace("-", "")

        return None

    def correct_product_code(self, extracted_item, table_data):
        best_match, best_score = None, 0
        description, qty, amount = (
            extracted_item["description"],
            extracted_item["qty"],
            extracted_item["amount"],
        )

        logging.info(f"Correcting product code for item: {extracted_item}")

        for table_item in table_data:
            logging.info(f"Comparing with table item: {table_item}")
            if qty == table_item["qty"] and abs(amount - table_item["amount"]) < 0.01:
                similarity_score = fuzz.partial_ratio(
                    description.lower(), table_item["description"].lower()
                )
                logging.info(f"Similarity score: {similarity_score}")
                if similarity_score > best_score:
                    best_score, best_match = (
                        similarity_score,
                        table_item["product_code"],
                    )

        logging.info(f"Best match: {best_match}, Best score: {best_score}")
        return best_match if best_match else extracted_item["product_code"]

    def process_data(self, data, customer_name):
        try:
            order = data.result()
            result_data = {"customer_name": customer_name, "order_line_items": []}
            extracted_items, table_items = [], []

            for invoice_document in order.documents:
                purchase_order = self.find_purchase_order(invoice_document)
                if not purchase_order or len(purchase_order) <= 6:
                    purchase_order = self.extract_purchase_order_number(order)

                result_data["purchase_order"] = purchase_order

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
                vendor_address = invoice_document.fields.get("VendorAddress")
                if vendor_address:
                    result_data["billing_address"] = Utility.splitted_address(
                        vendor_address.value.to_dict()
                    )
                items = invoice_document.fields.get("Items")
                if items and items.value:
                    for item in items.value:
                        product_code = self.adjust_product_code(
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
                        extracted_items.append(
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
                            }
                        )

            number_pattern = re.compile(r"^\d{1,3}(,\d{3})*(\.\d+)?$")
            for table in order.tables:
                rows = {cell.row_index: {} for cell in table.cells}
                for cell in table.cells:
                    rows[cell.row_index][cell.column_index] = cell.content.strip()

                for row_index in sorted(rows.keys()):
                    row = rows[row_index]
                    product_code = row.get(1, "").strip()
                    if not product_code:
                        continue

                    description = row.get(2, "").strip()
                    qty = (
                        int(row.get(0, "0").strip())
                        if row.get(0, "0").strip().isdigit()
                        else 0
                    )
                    amount_str = row.get(6, row.get(5, "0.0")).strip()
                    amount = (
                        float(amount_str.replace(",", ""))
                        if number_pattern.match(amount_str)
                        else 0.0
                    )
                    table_items.append(
                        {
                            "product_code": product_code.replace("\n", ""),
                            "description": description,
                            "qty": qty,
                            "amount": amount,
                            
                        }
                    )

            for item in extracted_items:
                item["product_code"] = self.correct_product_code(item, table_items)
                item["pdf_product_code"] = item["product_code"]
            result_data["order_line_items"] = extracted_items
            result_data["order_line_items"] = product_mapper.find_best_match(
                result_data["order_line_items"]
            )
            return result_data

        except Exception as ex:
            logging.error(f"{customer_name} process data failed. Reason: {str(ex)}")
            return None
