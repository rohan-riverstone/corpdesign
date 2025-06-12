import re
import logging
import base64
import pandas as pd
from io import BytesIO
from ..BL.part_number_map import product_mapper

class Everything2go:

    def transform_address(self, address_list,customer_name=None,addressee=None,phone_no=None):
        address1 = address_list[0] if len(address_list) > 0 else ""
        address2 = address_list[1] if len(address_list) > 2 else ""
        city_state_zip = address_list[-1] if len(address_list) > 1 else ""

        parts = city_state_zip.split(",")
        city = parts[0].strip() if len(parts) > 0 else ""

        state_zip = parts[1].strip().split() if len(parts) > 1 else []
        state = " ".join(state_zip[:-1]).strip() if len(state_zip) > 1 else ""
        zip_code = state_zip[-1] if len(state_zip) > 0 else ""
        if addressee and phone_no:
            return {
                "addressee": addressee,               
                "address1": customer_name + ", "+phone_no,
                "address2": address1,
                "city": city,
                "state": state,
                "zip_code": zip_code,
            }
        return {
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "zip_code": zip_code,
        }

    def extract_address(self, df, column_index):
        address, flag = [], False
        not_needed = ["@", ".com", "primary:", "alt:"]
        phone_no=None
        for _, row in df.iterrows():
            cell_value = str(row.iloc[column_index]).strip().lower()
            row_text = str(row).strip().lower()
            if "primary:" in row_text and flag:
                phone_no=cell_value.replace('primary:',"").strip()
            if "qty" in row_text or "unit price" in row_text or ("total" in row_text and 'model' in row_text):
                break
            if flag and pd.notna(row.iloc[column_index]):
                if not any(exclusion in cell_value for exclusion in not_needed):
                    address.append(cell_value)
            if cell_value.startswith(("sold to", "ship to")):
                flag = True
           
                
        if pd.notna(phone_no) and phone_no !='nan':
            address.append(phone_no)
        return address

    def process_data(self, data, customer_name):
        try:
            if isinstance(data, str):
                data = base64.b64decode(data)
            elif not isinstance(data, bytes):
                return None

            engine = (
                "xlrd"
                if data[:2] == b"\xd0\xcf"
                else "openpyxl" if data[:4] == b"PK\x03\x04" else None
            )
            if not engine:
                return None

            df = pd.read_excel(BytesIO(data), engine=engine)
            
            po_date, po_no, total, sold_to_col_idx, ship_to_idx = (
                None,
                None,
                None,
                None,
                None,
            )
            item_details, sold_to_address, ship_to_address = [], "", ""

            for index, row in df.iterrows():
                row_text = " ".join(
                    str(cell).lower().strip() for cell in row if pd.notna(cell)
                )

                if "po date" in row_text and "po number" in row_text:
                    po_date, po_no = row.dropna().iloc[1], row.dropna().iloc[3]
                if "total:" in row_text:
                    total = row.dropna().iloc[1]

                for col_idx, cell in enumerate(row):
                    if isinstance(cell, str):
                        if "sold to" in cell.lower():
                            sold_to_col_idx = col_idx
                        if "ship to" in cell.lower():
                            ship_to_idx = col_idx

                if sold_to_col_idx is not None and ship_to_idx is not None:
                    break

            if sold_to_col_idx is not None:
                sold_to_address = self.extract_address(df, sold_to_col_idx)
                
            if ship_to_idx is not None:
                ship_to_address = self.extract_address(df, ship_to_idx)
                phone_no=ship_to_address[-1]
                ship_to_address=ship_to_address[:len(ship_to_address)-1]
                print(ship_to_address,phone_no)
            start_extraction = False
            for _, row in df.iterrows():
                row_text = " ".join(
                    str(cell).lower().strip() for cell in row if pd.notna(cell)
                )

                if (
                    "qty" in row_text
                    and "model/item #" in row_text
                    and "total" in row_text
                ):
                    start_extraction = True
                    continue
                if start_extraction:
                    if "total:" in row_text:
                        break
                    non_nan_values = [
                        str(cell).strip() for cell in row if pd.notna(cell)
                    ]
                    if non_nan_values:
                        item_details.append(non_nan_values)

            order_line_items = []
            for item in item_details:
                product_codes = [code.strip() for code in item[1].split("+")]

                for product_code in product_codes:
                    order_line_items.append(
                        {
                            "product_code": product_code,
                            "description": item[2],
                            "qty": item[0],
                            "unit_price": item[3],
                            "amount": item[4],
                            "pdf_product_code": product_code,
                            
                            
                        }
                    )
            order_line_items=product_mapper.find_best_match(order_line_items)        
            return {
                "customer_name": customer_name,
                "purchase_order": po_no,
                "invoice_date": po_date,
                "shipping_address": (
                    self.transform_address(ship_to_address[2:],ship_to_address[0],ship_to_address[1],phone_no)
                    if ship_to_address
                    else {}
                ),
                "billing_address": (
                    self.transform_address(sold_to_address)
                    if sold_to_address
                    else {}
                ),
                "order_line_items": order_line_items,
            }
        except Exception as ex:
            logging.info(f"Everything2go process data failed. Reason: {str(ex)}")
            return None
