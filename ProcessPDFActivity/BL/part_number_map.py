import json
import re

class ProductCodeMapper:
    def __init__(self, group_file="ProcessPDFActivity/input_data/group.json", component_file="ProcessPDFActivity/input_data/component.json"):
        self.color_key_words = {
            "blanco", "blanc de gris", "espresso", "grigio", "grey", "miele",
            "noce", "black", "white", "two-tone grey", "sand"
        }
        
        self.keyword_map = {
            'noche': "noce",
            'bdg': "blanc de gris",
            'grigio': 'grigio,grey',
            'blanc di gris': 'blanc de gris'
        }
        
        self.group_data = self.load_json(group_file)
        self.component_data = self.load_json(component_file)

    def load_json(self, file_path):
        """Loads JSON data from a file."""
        with open(file_path, 'r') as file:
            return json.load(file)

    def clean_description(self, description):
        """Cleans and normalizes a description."""
        return re.sub(r'[-/]', ' ', description).lower()

    def extract_keywords(self, description):
        """Extracts relevant color-related keywords from a product description."""
        if not description:
            return set()
        
        description = self.clean_description(description)
        
        for key, value in self.keyword_map.items():
            description = description.replace(key, value)
        
        return {kw for kw in self.color_key_words if kw in description}

    def find_best_match(self, product_list):
        """Finds the best matching product based on exact and partial matches."""
        results = product_list  
        
        for product in results:
            product_code = product["product_code"]
            product_desc = product["description"]
            
            print(f"Processing Product: {product_code}")
            
            if product_code in self.group_data:
                print(f"Exact match found in group_data: {product_code}")
                product["product_code"] = product_code
                continue
            
            print(f"No exact match found for {product_code}, proceeding with partial matching...")
            
            product_keywords = self.extract_keywords(product_desc)
            print(f"Extracted Keywords: {product_keywords}")

            matching_groups = [key for key in self.group_data if key.startswith(product_code)]
            
            if len(matching_groups) == 1:
                product["product_code"] = matching_groups[0]
                continue
            elif matching_groups:
                best_match = self.find_best_keyword_match(matching_groups, self.group_data, product_keywords)
                if best_match:
                    product["product_code"] = best_match
                    continue
            
            if product_code in self.component_data:
                print(f"Exact match found in component_data: {product_code}")
                product["product_code"] = product_code
                continue
            
            matching_components = [key for key in self.component_data if key.startswith(product_code)]
            
            if len(matching_components) == 1:
                product["product_code"] = matching_components[0]
                continue
            elif matching_components:
                best_match = self.find_best_keyword_match(matching_components, self.component_data, product_keywords)
                if best_match:
                    product["product_code"] = best_match
                    continue
            
            print(f"No matches found for {product_code}, keeping original.")
        
        return results

    def find_best_keyword_match(self, matching_keys, data_source, product_keywords):
        """Finds the best match among multiple partial matches based on keyword similarity."""
        best_match = None
        best_match_score = 0  

        for match in matching_keys:
            match_desc = data_source.get(match, "")
            
            if isinstance(match_desc, list):
                match_desc = " ".join(match_desc)
            
            match_desc = self.clean_description(match_desc)
            match_keywords = self.extract_keywords(match_desc)
            
            if not match_keywords:
                continue

            score = len(match_keywords & product_keywords)
            
            if score > best_match_score:
                best_match = match
                best_match_score = score
        print(f"best_match: {best_match}")
        return best_match

product_mapper = ProductCodeMapper()