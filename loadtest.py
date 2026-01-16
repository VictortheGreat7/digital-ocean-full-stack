#!/usr/bin/env python3
"""
Load test script for World Clock API
Generates realistic traffic patterns to populate DB metrics
"""
import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Update this to your actual endpoint
BASE_URL = "http://your-app-url.com"  # or http://localhost:5000 for local

TIMEZONES = [
    "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney",
    "Asia/Dubai", "Asia/Singapore", "America/Sao_Paulo", "Asia/Kolkata",
    "Europe/Paris", "America/Los_Angeles", "Asia/Hong_Kong", "Europe/Berlin",
    "Invalid/Zone",  # Intentional error to generate 400s
]

ENDPOINTS = [
    ("/world-clocks", {}),
    ("/timezones", {}),
    ("/time", {"timezone": lambda: random.choice(TIMEZONES)}),
]

def make_request(session, run_num):
    """Single request with random endpoint/timezone"""
    endpoint, params = random.choice(ENDPOINTS)
    
    # Build params if it's a callable (for random values)
    request_params = {k: v() if callable(v) else v for k, v in params.items()}
    
    try:
        start = time.time()
        resp = session.get(f"{BASE_URL}{endpoint}", params=request_params, timeout=5)
        latency = (time.time() - start) * 1000
        
        status_emoji = "✅" if resp.status_code < 400 else "❌"
        print(f"{status_emoji} [{run_num:4d}] {endpoint:20s} → {resp.status_code} ({latency:.1f}ms)")
        
        return {
            "status": resp.status_code,
            "latency": latency,
            "endpoint": endpoint
        }
    except Exception as e:
        print(f"❌ [{run_num:4d}] Request failed: {e}")
        return {"status": 0, "latency": 0, "endpoint": endpoint}

def run_load_test(duration_seconds=300, concurrent_users=10):
    """
    Run load test
    - duration_seconds: how long to run (default 5min)
    - concurrent_users: parallel requests
    """
    print(f"🚀 Starting load test: {duration_seconds}s, {concurrent_users} concurrent users")
    print(f"   Target: {BASE_URL}")
    print("=" * 70)
    
    session = requests.Session()
    start_time = time.time()
    request_count = 0
    
    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = []
        
        while (time.time() - start_time) < duration_seconds:
            # Submit a new request
            future = executor.submit(make_request, session, request_count)
            futures.append(future)
            request_count += 1
            
            # Small delay between submissions (adjust for desired RPS)
            time.sleep(random.uniform(0.05, 0.2))  # ~5-20 RPS per user
            
            # Collect completed futures periodically
            if len(futures) > 100:
                done_futures = [f for f in futures if f.done()]
                futures = [f for f in futures if not f.done()]
        
        # Wait for remaining
        print("\n⏳ Waiting for remaining requests...")
        for future in as_completed(futures):
            future.result()
    
    elapsed = time.time() - start_time
    print("=" * 70)
    print(f"✅ Load test complete!")
    print(f"   Total requests: {request_count}")
    print(f"   Duration: {elapsed:.1f}s")
    print(f"   Avg RPS: {request_count/elapsed:.1f}")

if __name__ == "__main__":
    # Quick test (30 seconds, 5 users)
    run_load_test(duration_seconds=30, concurrent_users=5)
    
    # For serious load, use:
    # run_load_test(duration_seconds=600, concurrent_users=20)