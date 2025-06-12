from ..Models.office_interiors import OfficeInt
from ..Models.madison_liq import MadisonLiq
from ..Models.atlanta_office_liquiators import AtlandaLiq
from ..Models.office_furniture_4_sale import OfficeFurniture4Sale
from ..Models.kul import Kul
from ..Models.freedman_office_furniture import FreedmanOfficeFurniture
from ..Models.office_furniture_solutions_of_florida import OFSOF
from ..Models.dallas_desk import DallasDesk
from ..Models.boca_business_furniture import BocaFurniture
from ..Models.everything_2_go import Everything2go
from ..Models.compass_office_solutions import CompassOfficeSolution
from ..Models.office_furniture_expo import OfficeFurniture
from ..Models.cds import CommercialDesignServices

class Rules:
    NAME_RULES = {
    'office furniture outlet': "Office Furniture Outlet (AL)",
    'atlanta office liquidators inc': "Atlanta Office Liquidators Inc.",
    'michalsen office furniture inc.': "Michalsen Office Furniture",
    'office systems installation attn : angela hutchinson': "AI CORPORATE INTERIORS",
    'aoli': 'Atlanta Office Liquidators Inc.',
    'atlanta office interiors/ liquidators aoli': "Atlanta Office Liquidators Inc.",
    'madison liquidators': "Madison Liquidators LLC",
    'officefurniture4sale.com': "Office Furniture 4 Sale",
    "freedman's office furniture": "Freedman's Office Furniture-TAMPA",
    'dallas desk inc': 'Dallas Desk, Inc.',
    'dallas desk warehouse': 'Dallas Desk, Inc.',
    'kul office furniture': 'Kul Office Furniture',
    'office furniture solutions of fl llc': 'Office Furniture Solutions',
    'office furniture solutions': 'Office Furniture Solutions',
    'boca business furniture, inc': 'Boca Business Furniture, Inc.',
    'everything2go.com, llc': "Everything2go.com LLC",
    'office 4 furniture sale': "Office Furniture 4 Sale",
    'compass a better way':'Compass Office Solutions',
    'office furniture expo':'Office Furniture Expo (GA)',
    'CCS':'Commercial Design Services',
}

    MODEL_RULES = {
        'Kul Office Furniture': Kul,
        'Office Interiors of South Carolina LLC': OfficeInt,
        'Atlanta Office Liquidators Inc.': AtlandaLiq,
        'Madison Liquidators LLC': MadisonLiq,
        'Office Furniture 4 Sale': OfficeFurniture4Sale,
        "Freedman's Office Furniture-TAMPA": FreedmanOfficeFurniture,
        "Office Furniture Solutions": OFSOF,
        "Dallas Desk, Inc.": DallasDesk,
        "Everything2go.com LLC": Everything2go,
        'Boca Business Furniture, Inc.': BocaFurniture,
        'Compass Office Solutions': CompassOfficeSolution,
        'Office Furniture Expo (GA)':OfficeFurniture,
        'Commercial Design Services': CommercialDesignServices

    }

    @classmethod
    def adjust_customer_name(cls, name: str) -> str:
        return cls.NAME_RULES.get(name, name)

    @classmethod
    def get_customer_name(cls, fields, result):
        for key in ["ShippingAddressRecipient", "CustomerName", "VendorName", "VendorAddressRecipient"]:
            value = fields.get(key)
            if value and hasattr(value, "value") and value.value.strip():
                customer_name = cls.adjust_customer_name(value.value.replace('\n',' '))
                print("customer_name",customer_name.lower())
                if customer_name in cls.MODEL_RULES:
                    print("class,customer_name",customer_name)
                    return customer_name

        return cls.get_customer_name_from_bounding(result)

    @classmethod
    def match_customer_name(cls, extracted_name):
        if not extracted_name:
            return None

        return next((value for key, value in cls.NAME_RULES.items() if key.lower() in extracted_name.lower()), None)

    @classmethod
    def get_customer_name_from_bounding(cls, result):
        min_x, max_x = 0.0, 3.5
        min_y, max_y = 0.0, 3.0
        extracted_words = []

        for page in result.pages:
            for item in page.lines:
                text = item.content.strip()
                polygon = item.polygon
                if not polygon:
                    continue

                x_coords, y_coords = zip(*polygon)
                if (
                    min_x <= min(x_coords) <= max_x and min_x <= max(x_coords) <= max_x and
                    min_y <= min(y_coords) <= max_y and min_y <= max(y_coords) <= max_y
                    ):
                    extracted_words.append(text)

        if not extracted_words:
            return None

        final_text = " ".join(extracted_words)
        print("final_text :", final_text)
        return cls.match_customer_name(final_text)

    @classmethod
    def map_models(cls, poller, customer_name: str):
        model_class = cls.MODEL_RULES.get(customer_name)
        return model_class().process_data(poller, customer_name) if model_class else None