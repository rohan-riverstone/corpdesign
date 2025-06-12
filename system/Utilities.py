import base64
import pandas as pd
from io import BytesIO 

class Utility: 
        
    @staticmethod    
    def splitted_address(address, flag=False):
        city = address.get("city", "")
        if not city:  
            city = address.get("city_district", "")
        if flag :            
            return [{
                "addressee":None,
                "address1": "",
                "address2": address.get('street_address',''),
                "city": city,
                "state": address.get("state", ""),
                "zip_code": str(address.get("postal_code", ""))
            }]
        else:
            return [{
                "address1": str(address.get("house_number", "")),
                "address2": address.get("road", ""),
                "city": city,
                "state": address.get("state", ""),
                "zip_code": str(address.get("postal_code", ""))
            }]


 
    @staticmethod
    def get_cusotmer_name(data):
        if isinstance(data, str):  
            data = base64.b64decode(data)
        elif not isinstance(data, bytes):
            return None
        
        engine = 'xlrd' if data[:2] == b'\xd0\xcf' else 'openpyxl' if data[:4] == b'PK\x03\x04' else None
        if not engine:
            return None
        
        df = pd.read_excel(BytesIO(data), engine=engine)
        for index, row in df.iterrows():
            non_nan_values = row.dropna()  
            if not non_nan_values.empty:   
                first_key = non_nan_values.index[0]  
                print(first_key)
                return first_key.strip().lower()

    
    @staticmethod
    def generate_total(data):
        subject = "TEST - "
        subject_parts = []
        has_order = False 
        for data_item in data:
            orderline_item = data_item.get('result', {}).get('order_line_item', [])
            sales_order = data_item.get('result', {}).get("orderNumber", "")
            purchase_order = data_item.get('result', {}).get('purchase_order', '')

            if purchase_order and sales_order:
                has_order = True
                subject_parts.append(f"({purchase_order}/{sales_order})")
    
            total = 0
            success = 0
            failure = 0

            for item in orderline_item:
                total += 1
                if item.get('status') == 'inserted':
                    success += 1
                else:
                    failure += 1

            if orderline_item:
                data_item['total'] = total
                data_item['success'] = success
                data_item['failure'] = failure

        subject += ", ".join(subject_parts) if has_order else "FAILURE"  

        return data, subject
