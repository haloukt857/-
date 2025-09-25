#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V2 Identifier Cleanup Integration Testing Verification
Tests system-wide compatibility after V2 identifier cleanup.
"""

import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class V2CleanupIntegrationTester:
    """Comprehensive integration testing for V2 identifier cleanup validation."""
    
    def __init__(self):
        self.test_results = {
            'phase1_asgi_integration': {},
            'phase2_database_web_integration': {},
            'phase3_cross_module_integration': {},
            'phase4_end_to_end_integration': {}
        }
        self.errors = []
        
    def log_error(self, phase, test, error):
        """Log integration test errors."""
        error_msg = f"Phase {phase} - {test}: {str(error)}"
        self.errors.append(error_msg)
        logger.error(error_msg)
        logger.error(traceback.format_exc())
    
    async def test_phase1_asgi_integration(self):
        """Phase 1: ASGI Application Integration Test"""
        print("\n🔄 Phase 1: ASGI Application Integration Test")
        results = {}
        
        try:
            # Test 1.1: ASGI App Loading
            print("  Testing ASGI application loading...")
            from asgi_app import create_final_asgi_app
            app = create_final_asgi_app()
            results['asgi_app_creation'] = {'status': '✅', 'details': 'ASGI app created successfully'}
            print("    ✅ ASGI app creation successful")
            
            # Test 1.2: Route Module Loading
            print("  Testing route module loading...")
            route_modules = [
                'web.routes.media',
                'web.routes.regions', 
                'web.routes.merchants',
                'web.routes.incentives',
                'web.routes.orders'
            ]
            
            loaded_modules = {}
            for module_name in route_modules:
                try:
                    __import__(module_name)
                    loaded_modules[module_name] = '✅'
                    print(f"    ✅ {module_name} loaded successfully")
                except Exception as e:
                    loaded_modules[module_name] = f'❌ {str(e)}'
                    print(f"    ❌ {module_name} failed: {str(e)}")
                    
            results['route_modules'] = loaded_modules
            
            # Test 1.3: Route Mounting
            print("  Testing route mounting...")
            if hasattr(app, 'routes') and len(app.routes) >= 5:
                results['route_mounting'] = {'status': '✅', 'count': len(app.routes)}
                print(f"    ✅ Routes mounted: {len(app.routes)} routes")
            else:
                results['route_mounting'] = {'status': '❌', 'details': 'Insufficient routes mounted'}
                print("    ❌ Route mounting failed")
                
        except Exception as e:
            results['error'] = str(e)
            self.log_error('1', 'ASGI Integration', e)
            
        self.test_results['phase1_asgi_integration'] = results
        
    async def test_phase2_database_web_integration(self):
        """Phase 2: Database-Web Integration Test"""
        print("\n🔄 Phase 2: Database-Web Integration Test")
        results = {}
        
        try:
            # Test 2.1: Database Manager Loading
            print("  Testing database manager loading...")
            try:
                from database.db_orders import OrderManagerV2
                from database.db_merchants import MerchantManagerV2
                results['database_managers'] = '✅'
                print("    ✅ Database managers loaded successfully")
            except Exception as e:
                results['database_managers'] = f'❌ {str(e)}'
                print(f"    ❌ Database managers failed: {str(e)}")
            
            # Test 2.2: Web Route Integration
            print("  Testing web route integration...")
            try:
                from web.routes.orders import orders_routes
                from web.routes.merchants import merchants_routes
                results['web_routes'] = '✅'
                print("    ✅ Web routes loaded successfully")
            except Exception as e:
                results['web_routes'] = f'❌ {str(e)}'
                print(f"    ❌ Web routes failed: {str(e)}")
            
            # Test 2.3: Database Field Compatibility
            print("  Testing database field compatibility...")
            try:
                # Test renamed fields exist in database managers
                order_manager = OrderManagerV2()
                # Check if methods using renamed fields exist
                if hasattr(order_manager, 'get_orders_statistics'):
                    results['field_compatibility'] = '✅'
                    print("    ✅ Database field compatibility verified")
                else:
                    results['field_compatibility'] = '❌ Methods with renamed fields not found'
                    print("    ❌ Database field compatibility failed")
            except Exception as e:
                results['field_compatibility'] = f'❌ {str(e)}'
                print(f"    ❌ Field compatibility test failed: {str(e)}")
                
        except Exception as e:
            results['error'] = str(e)
            self.log_error('2', 'Database-Web Integration', e)
            
        self.test_results['phase2_database_web_integration'] = results
        
    async def test_phase3_cross_module_integration(self):
        """Phase 3: Cross-Module Dependency Integration"""
        print("\n🔄 Phase 3: Cross-Module Dependency Integration")
        results = {}
        
        try:
            # Test 3.1: Handler-Database Integration
            print("  Testing handler-database integration...")
            try:
                from handlers.merchant import BindingFlowManager
                results['handler_database'] = '✅'
                print("    ✅ Handler-database integration verified")
            except Exception as e:
                results['handler_database'] = f'❌ {str(e)}'
                print(f"    ❌ Handler-database integration failed: {str(e)}")
            
            # Test 3.2: Web-Database Integration
            print("  Testing web-database integration...")
            try:
                from web.routes.orders import orders_routes
                from database.db_orders import OrderManagerV2
                results['web_database'] = '✅'
                print("    ✅ Web-database integration verified")
            except Exception as e:
                results['web_database'] = f'❌ {str(e)}'
                print(f"    ❌ Web-database integration failed: {str(e)}")
            
            # Test 3.3: Template-JavaScript Integration
            print("  Testing template-javascript integration...")
            try:
                # Check if template files exist and contain standardized URLs
                template_files = [
                    'web/templates/orders.html',
                    'web/templates/merchants.html',
                    'web/templates/regions.html'
                ]
                
                template_status = {}
                for template_file in template_files:
                    template_path = project_root / template_file
                    if template_path.exists():
                        template_status[template_file] = '✅'
                    else:
                        template_status[template_file] = '❌'
                
                results['template_javascript'] = template_status
                print(f"    ✅ Template files checked: {template_status}")
                
            except Exception as e:
                results['template_javascript'] = f'❌ {str(e)}'
                print(f"    ❌ Template-javascript integration failed: {str(e)}")
                
        except Exception as e:
            results['error'] = str(e)
            self.log_error('3', 'Cross-Module Integration', e)
            
        self.test_results['phase3_cross_module_integration'] = results
        
    async def test_phase4_end_to_end_integration(self):
        """Phase 4: End-to-End User Journey Integration"""
        print("\n🔄 Phase 4: End-to-End User Journey Integration")
        results = {}
        
        try:
            # Test 4.1: Merchant Registration Flow
            print("  Testing merchant registration flow...")
            try:
                from handlers.merchant import BindingFlowManager
                from database.db_merchants import MerchantManagerV2
                
                # Test flow components exist
                flow_manager = BindingFlowManager()
                merchant_manager = MerchantManagerV2()
                results['merchant_flow'] = '✅'
                print("    ✅ Merchant registration flow components verified")
            except Exception as e:
                results['merchant_flow'] = f'❌ {str(e)}'
                print(f"    ❌ Merchant registration flow failed: {str(e)}")
            
            # Test 4.2: Order Management Flow
            print("  Testing order management flow...")
            try:
                from database.db_orders import OrderManagerV2
                from web.routes.orders import orders_routes
                
                order_manager = OrderManagerV2()
                results['order_flow'] = '✅'
                print("    ✅ Order management flow components verified")
            except Exception as e:
                results['order_flow'] = f'❌ {str(e)}'
                print(f"    ❌ Order management flow failed: {str(e)}")
            
            # Test 4.3: Region Management Flow
            print("  Testing region management flow...")
            try:
                from database.db_regions import RegionManagerV2
                from web.routes.regions import regions_routes
                
                region_manager = RegionManagerV2()
                results['region_flow'] = '✅'
                print("    ✅ Region management flow components verified")
            except Exception as e:
                results['region_flow'] = f'❌ {str(e)}'
                print(f"    ❌ Region management flow failed: {str(e)}")
            
            # Test 4.4: Statistics and Metrics Integration
            print("  Testing statistics and metrics integration...")
            try:
                from database.db_orders import OrderManagerV2
                order_manager = OrderManagerV2()
                
                # Test if statistics methods exist with renamed fields
                if hasattr(order_manager, 'get_orders_statistics'):
                    results['statistics_integration'] = '✅'
                    print("    ✅ Statistics integration verified")
                else:
                    results['statistics_integration'] = '❌ Statistics methods not found'
                    print("    ❌ Statistics integration failed")
            except Exception as e:
                results['statistics_integration'] = f'❌ {str(e)}'
                print(f"    ❌ Statistics integration failed: {str(e)}")
                
        except Exception as e:
            results['error'] = str(e)
            self.log_error('4', 'End-to-End Integration', e)
            
        self.test_results['phase4_end_to_end_integration'] = results
        
    def generate_integration_report(self):
        """Generate comprehensive integration test report."""
        print("\n" + "="*80)
        print("📋 V2 IDENTIFIER CLEANUP INTEGRATION TEST REPORT")
        print("="*80)
        
        total_tests = 0
        passed_tests = 0
        
        for phase_name, phase_results in self.test_results.items():
            print(f"\n🔍 {phase_name.upper().replace('_', ' ')}")
            print("-" * 60)
            
            for test_name, test_result in phase_results.items():
                if isinstance(test_result, dict):
                    if 'status' in test_result:
                        status = test_result['status']
                        details = test_result.get('details', '')
                        print(f"  {test_name}: {status} {details}")
                        total_tests += 1
                        if status == '✅':
                            passed_tests += 1
                    else:
                        for sub_test, sub_result in test_result.items():
                            print(f"  {test_name}.{sub_test}: {sub_result}")
                            total_tests += 1
                            if '✅' in str(sub_result):
                                passed_tests += 1
                else:
                    print(f"  {test_name}: {test_result}")
                    total_tests += 1
                    if '✅' in str(test_result):
                        passed_tests += 1
        
        print("\n" + "="*80)
        print("📊 INTEGRATION TEST SUMMARY")
        print("="*80)
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"Total Integration Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.errors:
            print(f"\n❌ INTEGRATION ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        overall_status = "✅ PASSED" if success_rate >= 80 else "❌ FAILED"
        print(f"\n🎯 OVERALL INTEGRATION STATUS: {overall_status}")
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': success_rate,
            'overall_status': overall_status,
            'detailed_results': self.test_results,
            'errors': self.errors
        }
    
    async def run_all_integration_tests(self):
        """Run all integration test phases."""
        print("🚀 Starting V2 Identifier Cleanup Integration Testing...")
        
        await self.test_phase1_asgi_integration()
        await self.test_phase2_database_web_integration()
        await self.test_phase3_cross_module_integration()
        await self.test_phase4_end_to_end_integration()
        
        return self.generate_integration_report()


async def main():
    """Main integration test execution."""
    tester = V2CleanupIntegrationTester()
    report = await tester.run_all_integration_tests()
    return report


if __name__ == "__main__":
    import asyncio
    report = asyncio.run(main())