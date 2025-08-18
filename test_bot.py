#!/usr/bin/env python3
"""
Test script for Token Holder Bot

This script tests the basic functionality of the bot components
without actually starting the Telegram bot.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_config():
    """Test configuration loading"""
    print("🔧 Testing Configuration...")
    
    try:
        from config import Config
        Config.validate()
        print("✅ Configuration validated successfully")
        print(f"   Token Contract: {Config.TOKEN_CONTRACT_ADDRESS}")
        print(f"   Admin Users: {len(Config.ADMIN_USER_IDS)}")
        return True
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_database():
    """Test database connection"""
    print("\n🗄️ Testing Database Connection...")
    
    try:
        from database import Database
        db = Database()
        print("✅ Database connection successful")
        
        # Test basic operations
        threshold = db.get_minimum_usd_threshold()
        print(f"   Current USD threshold: ${threshold}")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_solscan_api():
    """Test SOLSCAN API connection"""
    print("\n🔌 Testing SOLSCAN API...")
    
    try:
        from solscan_api import SolscanAPI
        api = SolscanAPI()
        
        # Test token info
        token_info = api.get_token_info("9M7eYNNP4TdJCmMspKpdbEhvpdds6E5WFVTTLjXfVray")
        if token_info:
            print("✅ SOLSCAN API connection successful")
            print(f"   Token: {token_info.get('name', 'Unknown')}")
            print(f"   Symbol: {token_info.get('symbol', 'Unknown')}")
        else:
            print("⚠️ SOLSCAN API connected but no token info returned")
        
        return True
    except Exception as e:
        print(f"❌ SOLSCAN API error: {e}")
        return False

def test_snapshot_service():
    """Test snapshot service"""
    print("\n📸 Testing Snapshot Service...")
    
    try:
        from snapshot_service import SnapshotService
        service = SnapshotService()
        print("✅ Snapshot service initialized successfully")
        
        # Test stats
        stats = service.get_snapshot_stats()
        print(f"   Total holders: {stats.get('total_holders', 0)}")
        
        service.close()
        return True
    except Exception as e:
        print(f"❌ Snapshot service error: {e}")
        return False

def test_scheduler():
    """Test scheduler"""
    print("\n⏰ Testing Scheduler...")
    
    try:
        from scheduler import SnapshotScheduler
        scheduler = SnapshotScheduler()
        print("✅ Scheduler initialized successfully")
        
        # Test next run times
        next_runs = scheduler.get_next_run_times()
        print("   Next scheduled runs:")
        for task, time in next_runs.items():
            if time:
                print(f"     {task}: {time}")
        
        scheduler.close()
        return True
    except Exception as e:
        print(f"❌ Scheduler error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Token Holder Bot - Component Tests\n")
    print("=" * 50)
    
    tests = [
        test_config,
        test_database,
        test_solscan_api,
        test_snapshot_service,
        test_scheduler
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Bot is ready to run.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
