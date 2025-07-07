"""
Integration test to verify library functionality
"""

import sys
from pathlib import Path

# Add project root to path for testing
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all public API imports work"""
    print("Testing imports...")
    
    try:
        # Test core imports
        from src.surreal_commands import (
            command, registry, submit_command, 
            get_command_status_sync, wait_for_command_sync,
            CommandStatus, CommandResult
        )
        print("✅ Core API imports successful")
        
        # Test advanced imports
        from src.surreal_commands import (
            CommandService, command_service,
            CommandExecutor, db_connection
        )
        print("✅ Advanced API imports successful")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_decorator():
    """Test command decorator functionality"""
    print("\nTesting @command decorator...")
    
    try:
        from src.surreal_commands import command, registry
        from pydantic import BaseModel
        
        class TestInput(BaseModel):
            value: str
        
        class TestOutput(BaseModel):
            result: str
        
        @command("test_decorator")
        def test_function(input_data: TestInput) -> TestOutput:
            return TestOutput(result=f"Processed: {input_data.value}")
        
        # Check if command was registered
        commands = registry.get_all_commands()
        test_commands = [cmd for cmd in commands if cmd.name == "test_decorator"]
        
        if test_commands:
            print("✅ Command decorator registration successful")
            print(f"   Registered as: {test_commands[0].app_id}.{test_commands[0].name}")
            return True
        else:
            print("❌ Command not found in registry")
            return False
            
    except Exception as e:
        print(f"❌ Decorator test failed: {e}")
        return False

def test_registry():
    """Test registry functionality"""
    print("\nTesting registry...")
    
    try:
        from src.surreal_commands import registry
        
        # Get all commands
        commands = registry.get_all_commands()
        print(f"✅ Registry contains {len(commands)} commands")
        
        # List commands by app
        apps = registry.list_commands()
        print(f"✅ Commands organized by {len(apps)} apps:")
        for app_name, app_commands in apps.items():
            print(f"   {app_name}: {list(app_commands.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Registry test failed: {e}")
        return False

def test_api_structure():
    """Test that API has expected structure"""
    print("\nTesting API structure...")
    
    try:
        import src.surreal_commands as cc
        
        # Check __all__ exports
        expected_exports = [
            'registry', 'command', 'submit_command', 'get_command_status',
            'get_command_status_sync', 'wait_for_command', 'wait_for_command_sync',
            'execute_command_sync', 'CommandStatus', 'CommandResult',
            'CommandService', 'command_service', 'CommandRegistryItem',
            'CommandExecutor', 'db_connection'
        ]
        
        missing_exports = []
        for export in expected_exports:
            if not hasattr(cc, export):
                missing_exports.append(export)
        
        if missing_exports:
            print(f"❌ Missing exports: {missing_exports}")
            return False
        else:
            print("✅ All expected exports present")
        
        # Test CommandStatus enum
        from src.surreal_commands import CommandStatus
        expected_statuses = ['NEW', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELED']
        for status in expected_statuses:
            if not hasattr(CommandStatus, status):
                print(f"❌ Missing CommandStatus.{status}")
                return False
        
        print("✅ CommandStatus enum complete")
        return True
        
    except Exception as e:
        print(f"❌ API structure test failed: {e}")
        return False

def test_cli_structure():
    """Test CLI module structure"""
    print("\nTesting CLI structure...")
    
    try:
        # Test CLI module imports
        from src.surreal_commands.cli import worker, dashboard, logs
        
        # Check main functions exist
        if hasattr(worker, 'main'):
            print("✅ Worker CLI has main() function")
        else:
            print("❌ Worker CLI missing main() function")
            return False
            
        if hasattr(dashboard, 'main'):
            print("✅ Dashboard CLI has main() function")
        else:
            print("❌ Dashboard CLI missing main() function")
            return False
            
        if hasattr(logs, 'main'):
            print("✅ Logs CLI has main() function")
        else:
            print("❌ Logs CLI missing main() function")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CLI structure test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Surreal Commands Library Integration Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_api_structure,
        test_decorator,
        test_registry,
        test_cli_structure
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Library is ready.")
        return True
    else:
        print("⚠️  Some tests failed. Review issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)