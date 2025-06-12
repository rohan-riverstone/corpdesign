"""
Copyright © 2022–2023 Riverstone Infotech. All rights reserved.

CORPDESIGN Order and all related materials, including but not limited to text, graphics, 
logos, images, and software, are protected by copyright and other intellectual 
property laws. Reproduction, distribution, display, or modification of any of the 
content for any purpose without express written permission from Riverstone Infotech 
is prohibited.

For permissions and inquiries, please contact:
software@riverstonetech.com

Unauthorized use or reproduction of CORPDESIGN Order may result in legal action.
"""
import os

class ConfigException(Exception): ...

class Config(object):

    _REQUIRED_ENV_VAR = [
        "ADI_ENDPOINT", "ADI_KEY",
        "CORPDESIGN_STORAGE_CON_STR", "AZURE_STORAGE_ACCOUNT",
        "AZURE_STORAGE_KEY", "NETSUITE_ENDPOINT_URL", "NETSUITE_CONSUMER_KEY",
        "NETSUITE_CONSUMER_SECRET", "NETSUITE_ACCESS_TOKEN", "NETSUITE_ACCESS_TOKEN_SECRET",
        "NETSUITE_REALM", "NETSUITE_OAUTH_SIGN_METHOD"
    ]
    
    _DEFAULT_CONFIG = {
        "verbose": False
    }

    
    def get_config(self, arg_config: dict) -> str:
        
        config = self._DEFAULT_CONFIG.copy()        
        for envvar in self._REQUIRED_ENV_VAR:
            if envvar not in os.environ:
                raise ConfigException(f"Please set the {envvar} environment variable")
            config[envvar.lower()] = os.environ[envvar]
        config.update(arg_config)
        return config
    
config=Config()    
config = config.get_config({'master_json_file': 'corpdesign_order.json',
                            'app_log': 'app_log.txt'})
    