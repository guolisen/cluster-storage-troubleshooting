#!/bin/bash
# volume_latency_monitor.sh - Script for monitoring volume operation latency
# This script is used by volume_testing_performance.py

# Parse command line arguments
test_dir=$1
duration=$2
operation_type=$3

echo "Starting latency monitoring for $duration seconds..."
echo "Timestamp,Operation,Size,Duration(s)" > "$test_dir/results.csv"

start_time=$(date +%s)
end_time=$((start_time + duration))
current_time=$start_time
iteration=0

while [ $current_time -lt $end_time ]; do
  # Write test
  if [ "$operation_type" = "write" ] || [ "$operation_type" = "all" ]; then
    write_start=$(date +%s.%N)
    dd if=/dev/zero of="$test_dir/write_test_$iteration" bs=1M count=1 2>/dev/null
    write_end=$(date +%s.%N)
    write_duration=$(echo "$write_end - $write_start" | bc)
    echo "$(date +%Y-%m-%d_%H:%M:%S),write,1M,$write_duration" >> "$test_dir/results.csv"
  fi
  
  # Read test
  if [ "$operation_type" = "read" ] || [ "$operation_type" = "all" ]; then
    if [ -f "$test_dir/write_test_$iteration" ]; then
      read_start=$(date +%s.%N)
      dd if="$test_dir/write_test_$iteration" of=/dev/null bs=1M 2>/dev/null
      read_end=$(date +%s.%N)
      read_duration=$(echo "$read_end - $read_start" | bc)
      echo "$(date +%Y-%m-%d_%H:%M:%S),read,1M,$read_duration" >> "$test_dir/results.csv"
    fi
  fi
  
  # Random small writes
  if [ "$operation_type" = "write" ] || [ "$operation_type" = "all" ]; then
    write_small_start=$(date +%s.%N)
    dd if=/dev/urandom of="$test_dir/small_test_$iteration" bs=4k count=10 2>/dev/null
    write_small_end=$(date +%s.%N)
    write_small_duration=$(echo "$write_small_end - $write_small_start" | bc)
    echo "$(date +%Y-%m-%d_%H:%M:%S),write_small,40K,$write_small_duration" >> "$test_dir/results.csv"
  fi
  
  # Metadata operation test (touch file, list dir)
  meta_start=$(date +%s.%N)
  touch "$test_dir/meta_test_$iteration" && ls -la "$test_dir/" >/dev/null
  meta_end=$(date +%s.%N)
  meta_duration=$(echo "$meta_end - $meta_start" | bc)
  echo "$(date +%Y-%m-%d_%H:%M:%S),metadata,0,$meta_duration" >> "$test_dir/results.csv"
  
  # Sleep a bit to avoid overwhelming the system
  sleep 2
  current_time=$(date +%s)
  iteration=$((iteration + 1))
done

# Analyze results
echo "Latency Monitoring Completed"
echo "Summary:"

if [ "$operation_type" = "write" ] || [ "$operation_type" = "all" ]; then
  echo "Write operations (1MB):"
  awk -F, '$2=="write" {sum+=$4; count++} END {print "  Average latency: " (count > 0 ? sum/count : "N/A") " seconds over " count " operations"}' "$test_dir/results.csv"
fi

if [ "$operation_type" = "read" ] || [ "$operation_type" = "all" ]; then
  echo "Read operations (1MB):"
  awk -F, '$2=="read" {sum+=$4; count++} END {print "  Average latency: " (count > 0 ? sum/count : "N/A") " seconds over " count " operations"}' "$test_dir/results.csv"
fi

if [ "$operation_type" = "write" ] || [ "$operation_type" = "all" ]; then
  echo "Small write operations (40KB):"
  awk -F, '$2=="write_small" {sum+=$4; count++} END {print "  Average latency: " (count > 0 ? sum/count : "N/A") " seconds over " count " operations"}' "$test_dir/results.csv"
fi

echo "Metadata operations:"
awk -F, '$2=="metadata" {sum+=$4; count++} END {print "  Average latency: " (count > 0 ? sum/count : "N/A") " seconds over " count " operations"}' "$test_dir/results.csv"

# Output complete - script ends here
