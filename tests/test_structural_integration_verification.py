#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Structural Integration Testing for V2 Identifier Cleanup
Tests system structural integrity without requiring runtime dependencies.
"""

import sys
import traceback
import importlib
import inspect
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class StructuralIntegrationTester:
    """Tests structural integrity of the V2 system after cleanup."""
    
    def __init__(self):
        self.test_results = {}
        self.errors = []
        self.structural_issues = []
        
    def test_database_managers_structure(self):
        """Test database manager class structure and methods."""
        print("\n🔍 Testing Database Manager Structure")
        results = {}
        
        manager_modules = {
            'OrderManager': 'database.db_orders',
            'MerchantManager': 'database.db_merchants',
            'RegionManager': 'database.db_regions',
            'UserManager': 'database.db_users',
            'IncentiveManager': 'database.db_incentives'
        }
        
        for manager_name, module_path in manager_modules.items():
            try:
                module = importlib.import_module(module_path)
                manager_class = getattr(module, manager_name)
                
                # Get all methods
                methods = [method for method in dir(manager_class) if not method.startswith('_')]
                results[manager_name] = {
                    'status': '✅',
                    'methods_count': len(methods),
                    'key_methods': methods[:10]  # First 10 methods
                }
                print(f"  ✅ {manager_name}: {len(methods)} methods")
                
            except Exception as e:
                results[manager_name] = {'status': '❌', 'error': str(e)}
                print(f"  ❌ {manager_name}: {str(e)}")
                self.errors.append(f"Database manager {manager_name}: {str(e)}")
        
        self.test_results['database_managers'] = results
        
    def test_web_routes_structure(self):
        """Test web route modules structure."""
        print("\n🔍 Testing Web Routes Structure")
        results = {}
        
        route_modules = [
            'web.routes.orders',
            'web.routes.merchants', 
            'web.routes.regions',
            'web.routes.incentives',
            'web.routes.media'
        ]
        
        for module_path in route_modules:
            try:
                module = importlib.import_module(module_path)
                
                # Check if routes variable exists
                has_routes = hasattr(module, f"{module_path.split('.')[-1]}_routes")
                route_var_name = f"{module_path.split('.')[-1]}_routes"
                
                if has_routes:
                    routes = getattr(module, route_var_name)
                    results[module_path] = {
                        'status': '✅',
                        'routes_variable': route_var_name,
                        'routes_count': len(routes) if hasattr(routes, '__len__') else 'N/A'
                    }
                    print(f"  ✅ {module_path}: Found {route_var_name}")
                else:
                    results[module_path] = {
                        'status': '⚠️',
                        'issue': f"No {route_var_name} found",
                        'available_attrs': [attr for attr in dir(module) if not attr.startswith('_')][:5]
                    }
                    print(f"  ⚠️ {module_path}: No {route_var_name} found")
                    
            except Exception as e:
                results[module_path] = {'status': '❌', 'error': str(e)}
                print(f"  ❌ {module_path}: {str(e)}")
                self.errors.append(f"Web route {module_path}: {str(e)}")
        
        self.test_results['web_routes'] = results
        
    def test_handlers_structure(self):
        """Test handler modules structure."""
        print("\n🔍 Testing Handlers Structure")
        results = {}
        
        handler_modules = [
            'handlers.user',
            'handlers.merchant', 
            'handlers.admin',
            'handlers.auto_reply'
        ]
        
        for module_path in handler_modules:
            try:
                module = importlib.import_module(module_path)
                
                # Check for key functions and classes
                functions = [name for name, obj in inspect.getmembers(module, inspect.isfunction) 
                            if not name.startswith('_')]
                classes = [name for name, obj in inspect.getmembers(module, inspect.isclass) 
                          if not name.startswith('_')]
                
                results[module_path] = {
                    'status': '✅',
                    'functions': len(functions),
                    'classes': len(classes),
                    'key_functions': functions[:5],
                    'key_classes': classes[:5]
                }
                print(f"  ✅ {module_path}: {len(functions)} functions, {len(classes)} classes")
                
            except Exception as e:
                results[module_path] = {'status': '❌', 'error': str(e)}
                print(f"  ❌ {module_path}: {str(e)}")
                self.errors.append(f"Handler {module_path}: {str(e)}")
        
        self.test_results['handlers'] = results
        
    def test_template_files_structure(self):
        """Test template files exist and contain expected patterns."""
        print("\n🔍 Testing Template Files Structure")
        results = {}
        
        template_files = [
            'web/templates/orders.html',
            'web/templates/merchants.html',
            'web/templates/regions.html',
            'web/templates/incentives.html'
        ]
        
        url_patterns = ['/orders', '/merchants', '/regions', '/incentives']
        
        for template_file in template_files:
            template_path = project_root / template_file
            try:
                if template_path.exists():
                    content = template_path.read_text(encoding='utf-8')
                    
                    # Check for URL patterns
                    found_patterns = [pattern for pattern in url_patterns if pattern in content]
                    
                    # Check for common HTML structures
                    has_table = '<table' in content
                    has_form = '<form' in content
                    has_script = '<script' in content
                    
                    results[template_file] = {
                        'status': '✅',
                        'size': len(content),
                        'url_patterns': found_patterns,
                        'has_table': has_table,
                        'has_form': has_form,
                        'has_script': has_script
                    }
                    print(f"  ✅ {template_file}: {len(content)} chars, patterns: {found_patterns}")
                else:
                    results[template_file] = {'status': '❌', 'error': 'File not found'}
                    print(f"  ❌ {template_file}: Not found")
                    
            except Exception as e:
                results[template_file] = {'status': '❌', 'error': str(e)}
                print(f"  ❌ {template_file}: {str(e)}")
                self.errors.append(f"Template {template_file}: {str(e)}")
        
        self.test_results['templates'] = results
        
    def test_import_dependencies(self):
        """Test critical import dependencies without instantiation."""
        print("\n🔍 Testing Import Dependencies")
        results = {}
        
        critical_imports = [
            'config',
            'database.db_connection',
            'web.app',
            'utils.keyboard_utils',
            'database.db_templates'
        ]
        
        for import_path in critical_imports:
            try:
                importlib.import_module(import_path)
                results[import_path] = {'status': '✅'}
                print(f"  ✅ {import_path}: Import successful")
            except Exception as e:
                results[import_path] = {'status': '❌', 'error': str(e)}
                print(f"  ❌ {import_path}: {str(e)}")
                self.errors.append(f"Import {import_path}: {str(e)}")
        
        self.test_results['imports'] = results
        
    def test_cross_module_references(self):
        """Test cross-module references are valid."""
        print("\n🔍 Testing Cross-Module References")
        results = {}
        
        # Test database managers can be imported by web routes
        try:
            from database.db_orders import OrderManager
            from web.routes.orders import orders_routes
            results['orders_cross_ref'] = {'status': '✅'}
            print("  ✅ Orders: Database-Web cross-reference valid")
        except Exception as e:
            results['orders_cross_ref'] = {'status': '❌', 'error': str(e)}
            print(f"  ❌ Orders cross-reference: {str(e)}")
        
        # Test handlers can import database managers
        try:
            from handlers.merchant import BindingFlowManager
            from database.db_merchants import MerchantManager
            results['merchant_cross_ref'] = {'status': '⚠️', 'note': 'BindingFlowManager needs bot parameter'}
            print("  ⚠️ Merchant: Handler-Database cross-reference valid (needs bot parameter)")
        except Exception as e:
            results['merchant_cross_ref'] = {'status': '❌', 'error': str(e)}
            print(f"  ❌ Merchant cross-reference: {str(e)}")
        
        # Test user handler functions exist
        try:
            from handlers.user import get_user_router, init_user_handler
            results['user_functions'] = {'status': '✅'}
            print("  ✅ User: Required functions available")
        except Exception as e:
            results['user_functions'] = {'status': '❌', 'error': str(e)}
            print(f"  ❌ User functions: {str(e)}")
        
        self.test_results['cross_references'] = results
        
    def generate_structural_report(self):
        """Generate comprehensive structural integrity report."""
        print("\n" + "="*80)
        print("📋 STRUCTURAL INTEGRATION TEST REPORT")
        print("="*80)
        
        total_tests = 0
        passed_tests = 0
        warning_tests = 0
        
        for category, category_results in self.test_results.items():
            print(f"\n🔍 {category.upper()}")
            print("-" * 60)
            
            for test_name, test_result in category_results.items():
                status = test_result.get('status', '❌')
                if status == '✅':
                    passed_tests += 1
                elif status == '⚠️':
                    warning_tests += 1
                    
                total_tests += 1
                
                if 'error' in test_result:
                    print(f"  {test_name}: {status} - {test_result['error']}")
                elif 'note' in test_result:
                    print(f"  {test_name}: {status} - {test_result['note']}")
                else:
                    details = []
                    if 'methods_count' in test_result:
                        details.append(f"{test_result['methods_count']} methods")
                    if 'size' in test_result:
                        details.append(f"{test_result['size']} chars")
                    if 'url_patterns' in test_result:
                        details.append(f"patterns: {test_result['url_patterns']}")
                    
                    detail_str = ', '.join(details) if details else ''
                    print(f"  {test_name}: {status} {detail_str}")
        
        print("\n" + "="*80)
        print("📊 STRUCTURAL INTEGRITY SUMMARY")
        print("="*80)
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        warning_rate = (warning_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Structural Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Warnings: {warning_tests}")
        print(f"Failed: {total_tests - passed_tests - warning_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        print(f"Warning Rate: {warning_rate:.1f}%")
        
        if self.errors:
            print(f"\n❌ STRUCTURAL ERRORS ({len(self.errors)}):")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"  • {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")
        
        # Determine overall status
        if success_rate >= 85:
            overall_status = "✅ EXCELLENT"
        elif success_rate >= 75:
            overall_status = "✅ GOOD"
        elif success_rate >= 60:
            overall_status = "⚠️ ACCEPTABLE"
        else:
            overall_status = "❌ NEEDS WORK"
            
        print(f"\n🎯 STRUCTURAL INTEGRITY STATUS: {overall_status}")
        
        # Specific recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if success_rate < 85:
            print(f"  • Fix critical import errors")
            print(f"  • Ensure all manager classes are properly exported")
            print(f"  • Verify web route modules structure")
        if warning_rate > 0:
            print(f"  • Address warning conditions in handlers")
            print(f"  • Review template URL patterns")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'warning_tests': warning_tests,
            'success_rate': success_rate,
            'overall_status': overall_status,
            'detailed_results': self.test_results,
            'errors': self.errors
        }
    
    def run_all_structural_tests(self):
        """Run all structural integrity tests."""
        print("🚀 Starting Structural Integration Testing...")
        
        self.test_database_managers_structure()
        self.test_web_routes_structure()
        self.test_handlers_structure()
        self.test_template_files_structure()
        self.test_import_dependencies()
        self.test_cross_module_references()
        
        return self.generate_structural_report()


def main():
    """Main structural test execution."""
    tester = StructuralIntegrationTester()
    report = tester.run_all_structural_tests()
    return report


if __name__ == "__main__":
    report = main()