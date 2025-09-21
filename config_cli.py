# config_cli.py - Configuration Management CLI Tool

import argparse
import yaml
from pathlib import Path
from config_manager import ConfigManager

def add_use_case(config_manager: ConfigManager, use_case_id: str, description: str = None):
    """Add a new use case to the configuration"""
    current_cases = config_manager.get_allowed_use_cases()
    
    if use_case_id in current_cases:
        print(f"⚠️  Use case '{use_case_id}' already exists")
        return False
    
    # Add to allowed use cases
    config_manager.config['access_control']['allowed_use_cases'].append(use_case_id)
    
    # Add description if provided
    if description:
        if 'use_case_descriptions' not in config_manager.config['access_control']:
            config_manager.config['access_control']['use_case_descriptions'] = {}
        config_manager.config['access_control']['use_case_descriptions'][use_case_id] = description
    
    # Save configuration
    save_config(config_manager)
    print(f"✅ Added use case '{use_case_id}'")
    return True

def remove_use_case(config_manager: ConfigManager, use_case_id: str):
    """Remove a use case from the configuration"""
    current_cases = config_manager.get_allowed_use_cases()
    
    if use_case_id not in current_cases:
        print(f"⚠️  Use case '{use_case_id}' not found")
        return False
    
    # Remove from allowed use cases
    config_manager.config['access_control']['allowed_use_cases'].remove(use_case_id)
    
    # Remove description if exists
    descriptions = config_manager.config['access_control'].get('use_case_descriptions', {})
    if use_case_id in descriptions:
        del descriptions[use_case_id]
    
    # Save configuration
    save_config(config_manager)
    print(f"✅ Removed use case '{use_case_id}'")
    return True

def list_use_cases(config_manager: ConfigManager):
    """List all current use cases"""
    cases = config_manager.get_allowed_use_cases()
    
    if not cases:
        print("No use cases configured")
        return
    
    print("📋 Current allowed use cases:")
    for case in cases:
        description = config_manager.get_use_case_description(case)
        print(f"   • {case}: {description}")

def save_config(config_manager: ConfigManager):
    """Save configuration back to file"""
    try:
        with open(config_manager.config_file, 'w') as file:
            yaml.dump(config_manager.config, file, default_flow_style=False, indent=2)
        print(f"💾 Configuration saved to {config_manager.config_file}")
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")

def validate_use_case(config_manager: ConfigManager, use_case_id: str):
    """Validate a specific use case ID"""
    is_allowed = config_manager.is_use_case_allowed(use_case_id)
    description = config_manager.get_use_case_description(use_case_id)
    
    if is_allowed:
        print(f"✅ Use case '{use_case_id}' is ALLOWED")
        print(f"   Description: {description}")
    else:
        print(f"❌ Use case '{use_case_id}' is DENIED")
        print(f"   Allowed use cases: {', '.join(config_manager.get_allowed_use_cases())}")

def bulk_add_use_cases(config_manager: ConfigManager, file_path: str):
    """Add use cases from a file (one per line, format: ID:Description)"""
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        
        added_count = 0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):  # Skip empty lines and comments
                continue
                
            if ':' in line:
                use_case_id, description = line.split(':', 1)
                use_case_id = use_case_id.strip()
                description = description.strip()
            else:
                use_case_id = line.strip()
                description = None
            
            if use_case_id:
                if add_use_case(config_manager, use_case_id, description):
                    added_count += 1
                else:
                    print(f"   Line {line_num}: Skipped '{use_case_id}' (already exists)")
        
        print(f"\n🎉 Bulk import complete: {added_count} use cases added")
        
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
    except Exception as e:
        print(f"❌ Error reading file: {e}")

def export_use_cases(config_manager: ConfigManager, file_path: str):
    """Export use cases to a file"""
    try:
        cases = config_manager.get_allowed_use_cases()
        
        with open(file_path, 'w') as file:
            file.write("# Use Case Export\n")
            file.write("# Format: USE_CASE_ID:Description\n\n")
            
            for case in cases:
                description = config_manager.get_use_case_description(case)
                file.write(f"{case}:{description}\n")
        
        print(f"✅ Exported {len(cases)} use cases to {file_path}")
        
    except Exception as e:
        print(f"❌ Error exporting use cases: {e}")

def reset_config(config_manager: ConfigManager):
    """Reset configuration to defaults"""
    response = input("⚠️  This will reset all configuration to defaults. Continue? (y/N): ")
    
    if response.lower() != 'y':
        print("❌ Reset cancelled")
        return
    
    try:
        # Create backup
        backup_file = f"{config_manager.config_file}.backup"
        with open(config_manager.config_file, 'r') as src, open(backup_file, 'w') as dst:
            dst.write(src.read())
        print(f"📋 Backup created: {backup_file}")
        
        # Reset to defaults
        config_manager.config = config_manager._get_default_config()
        save_config(config_manager)
        print("✅ Configuration reset to defaults")
        
    except Exception as e:
        print(f"❌ Error resetting configuration: {e}")

def main():
    """CLI for configuration management"""
    parser = argparse.ArgumentParser(
        description="Manage FastAPI Proxy Configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                              # List all use cases
  %(prog)s add "200000" -d "New mobile app"  # Add use case with description
  %(prog)s remove "100050"                   # Remove use case
  %(prog)s validate "100000"                 # Check if use case is allowed
  %(prog)s bulk-add use_cases.txt            # Import use cases from file
  %(prog)s export use_cases.txt              # Export use cases to file
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all use cases')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new use case')
    add_parser.add_argument('use_case_id', help='Use case ID to add')
    add_parser.add_argument('-d', '--description', help='Optional description')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove a use case')
    remove_parser.add_argument('use_case_id', help='Use case ID to remove')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a use case ID')
    validate_parser.add_argument('use_case_id', help='Use case ID to validate')
    
    # Bulk add command
    bulk_add_parser = subparsers.add_parser('bulk-add', help='Add use cases from file')
    bulk_add_parser.add_argument('file_path', help='Path to file containing use cases')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export use cases to file')
    export_parser.add_argument('file_path', help='Path to export file')
    
    # Show config command
    subparsers.add_parser('show', help='Show current configuration')
    
    # Reset command
    subparsers.add_parser('reset', help='Reset configuration to defaults')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Execute commands
    if args.command == 'list':
        list_use_cases(config_manager)
    elif args.command == 'add':
        add_use_case(config_manager, args.use_case_id, args.description)
    elif args.command == 'remove':
        remove_use_case(config_manager, args.use_case_id)
    elif args.command == 'validate':
        validate_use_case(config_manager, args.use_case_id)
    elif args.command == 'bulk-add':
        bulk_add_use_cases(config_manager, args.file_path)
    elif args.command == 'export':
        export_use_cases(config_manager, args.file_path)
    elif args.command == 'show':
        print("🔧 Current Configuration:")
        print(yaml.dump(config_manager.config, default_flow_style=False, indent=2))
    elif args.command == 'reset':
        reset_config(config_manager)

if __name__ == "__main__":
    main()