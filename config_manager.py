import yaml
import os
from typing import Dict, List, Any
from pathlib import Path

class ConfigManager:
    """Configuration manager for the FastAPI proxy system"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            self._create_default_config()
        
        try:
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
                return config
        except Exception as e:
            print(f"Error loading config file: {e}")
            return self._get_default_config()
    
    def _create_default_config(self):
        """Create default configuration file"""
        default_config = self._get_default_config()
        
        try:
            with open(self.config_file, 'w') as file:
                yaml.dump(default_config, file, default_flow_style=False, indent=2)
            print(f"Created default configuration file: {self.config_file}")
        except Exception as e:
            print(f"Error creating config file: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'proxy': {
                'host': '0.0.0.0',
                'port': 8001,
                'backend_url': 'http://localhost:8002'
            },
            'chat_server': {
                'host': '0.0.0.0',
                'port': 8002
            },
            'chainlit': {
                'host': '0.0.0.0',
                'port': 8000,
                'proxy_url': 'http://localhost:8001',
                'default_use_case_id': '100000'
            },
            'access_control': {
                'allowed_use_cases': [
                    '100000',
                    '100050', 
                    '101966',
                    '102550',
                    '103366'
                ],
                'use_case_descriptions': {
                    '100000': 'Primary client application',
                    '100050': 'Mobile application v2',
                    '101966': 'Analytics dashboard',
                    '102550': 'Admin panel interface',
                    '103366': 'External API integration'
                }
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'security': {
                'require_use_case_header': True,
                'case_sensitive_matching': False,
                'log_rejected_requests': True
            }
        }
    
    def get_allowed_use_cases(self) -> List[str]:
        """Get list of allowed use case IDs"""
        return self.config.get('access_control', {}).get('allowed_use_cases', [])
    
    def get_use_case_description(self, use_case_id: str) -> str:
        """Get description for a use case ID"""
        descriptions = self.config.get('access_control', {}).get('use_case_descriptions', {})
        return descriptions.get(use_case_id, f"Use case {use_case_id}")
    
    def get_proxy_config(self) -> Dict[str, Any]:
        """Get proxy server configuration"""
        return self.config.get('proxy', {})
    
    def get_chat_server_config(self) -> Dict[str, Any]:
        """Get chat server configuration"""
        return self.config.get('chat_server', {})
    
    def get_chainlit_config(self) -> Dict[str, Any]:
        """Get chainlit configuration"""
        return self.config.get('chainlit', {})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return self.config.get('security', {})
    
    def is_use_case_allowed(self, use_case_id: str) -> bool:
        """Check if use case ID is allowed"""
        allowed_cases = self.get_allowed_use_cases()
        security_config = self.get_security_config()
        
        if security_config.get('case_sensitive_matching', False):
            return use_case_id in allowed_cases
        else:
            return use_case_id.lower() in [case.lower() for case in allowed_cases]
    
    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()
        print("Configuration reloaded")

# Global config instance
config = ConfigManager()
