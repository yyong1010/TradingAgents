#!/usr/bin/env python3
"""
Integration Test Runner for Analysis History

This script runs the comprehensive integration tests for the analysis history
tracking feature, including end-to-end workflow testing, performance testing,
and error handling validation.

Usage:
    python tests/run_integration_tests.py
    python -m tests.run_integration_tests
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import logging
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('test.runner')

def check_prerequisites():
    """Check if all prerequisites for integration tests are met"""
    logger.info("🔍 Checking integration test prerequisites...")
    
    prerequisites_met = True
    issues = []
    
    # Check if MongoDB is available
    try:
        from web.utils.history_storage import get_history_storage
        history_storage = get_history_storage()
        if not history_storage.is_available():
            prerequisites_met = False
            issues.append("MongoDB/History storage is not available")
        else:
            logger.info("✅ History storage is available")
    except Exception as e:
        prerequisites_met = False
        issues.append(f"Failed to initialize history storage: {e}")
    
    # Check if required modules can be imported
    required_modules = [
        'web.utils.analysis_runner',
        'web.modules.analysis_history',
        'web.utils.report_exporter',
        'web.models.history_models'
    ]
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✅ Module {module} imported successfully")
        except ImportError as e:
            prerequisites_met = False
            issues.append(f"Failed to import {module}: {e}")
    
    # Check if test data directory exists
    test_data_dir = project_root / "data"
    if not test_data_dir.exists():
        logger.warning(f"⚠️ Test data directory {test_data_dir} does not exist, creating...")
        test_data_dir.mkdir(parents=True, exist_ok=True)
    
    return prerequisites_met, issues


def run_integration_tests():
    """Run the integration tests with proper setup and error handling"""
    logger.info("🚀 Starting Analysis History Integration Tests")
    logger.info("=" * 60)
    
    # Check prerequisites
    prerequisites_met, issues = check_prerequisites()
    
    if not prerequisites_met:
        logger.error("❌ Prerequisites not met:")
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("\n💡 Please ensure:")
        logger.error("  1. MongoDB is running and accessible")
        logger.error("  2. All required Python packages are installed")
        logger.error("  3. Environment variables are properly configured")
        return False
    
    logger.info("✅ All prerequisites met, starting tests...")
    
    # Import and run tests
    try:
        from tests.integration.test_history_integration import run_integration_tests
        
        start_time = time.time()
        success = run_integration_tests()
        end_time = time.time()
        
        duration = end_time - start_time
        logger.info(f"⏱️ Integration tests completed in {duration:.2f} seconds")
        
        if success:
            logger.info("🎉 All integration tests passed successfully!")
            logger.info("\n📋 Test Coverage Summary:")
            logger.info("  ✅ Complete analysis workflow with history saving")
            logger.info("  ✅ History page rendering with real database data")
            logger.info("  ✅ Search and filtering functionality")
            logger.info("  ✅ Download functionality for all formats")
            logger.info("  ✅ Performance testing with large datasets")
            logger.info("  ✅ Error handling and recovery scenarios")
            logger.info("  ✅ End-to-end user workflow simulation")
        else:
            logger.error("❌ Some integration tests failed")
            logger.error("Please check the detailed output above for specific failures")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Failed to run integration tests: {e}")
        logger.error("This might indicate a serious configuration or import issue")
        return False


def main():
    """Main entry point"""
    try:
        success = run_integration_tests()
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 INTEGRATION TESTS PASSED")
            print("=" * 60)
            print("All analysis history integration tests completed successfully!")
            print("The system is ready for production use.")
        else:
            print("\n" + "=" * 60)
            print("❌ INTEGRATION TESTS FAILED")
            print("=" * 60)
            print("Some tests failed. Please review the output above.")
            print("Fix the issues before deploying to production.")
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Integration tests interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error during test execution: {e}")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)