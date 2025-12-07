#!/bin/bash
# Load testing script

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
CONCURRENT_USERS="${CONCURRENT_USERS:-10}"
TOTAL_REQUESTS="${TOTAL_REQUESTS:-100}"

echo "Starting load test..."
echo "Base URL: $BASE_URL"
echo "Concurrent users: $CONCURRENT_USERS"
echo "Total requests: $TOTAL_REQUESTS"

# Example using Apache Bench (ab) or similar tool
# ab -n $TOTAL_REQUESTS -c $CONCURRENT_USERS $BASE_URL/healthz

# Or using curl in a loop
for i in $(seq 1 $TOTAL_REQUESTS); do
    curl -s "$BASE_URL/healthz" > /dev/null &
    if [ $((i % $CONCURRENT_USERS)) -eq 0 ]; then
        wait
    fi
done

wait
echo "Load test completed"


