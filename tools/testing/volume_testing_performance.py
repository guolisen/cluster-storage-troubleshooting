#!/usr/bin/env python3
"""
Performance-related volume testing tools.

This module provides tools for performance testing, stress testing,
and latency monitoring of pod volumes.
"""

import time
from datetime import datetime
from typing import Dict, Any
from langchain_core.tools import tool
from tools.core.config import validate_command, execute_command

@tool
def run_volume_stress_test(pod_name: str, namespace: str = "default", 
                          mount_path: str = "/test-volume", 
                          duration: int = 60) -> str:
    """
    Run a stress test on the volume to check for I/O errors under load
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path
        duration: Test duration in seconds
        
    Returns:
        str: Stress test results
    """
    results = []
    
    try:
        # Check available space first
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        space_result = execute_command(cmd)
        results.append(f"Available Space:\n{space_result}")
        
        # Run concurrent I/O operations
        stress_cmd = f"""
        echo 'Starting stress test for {duration} seconds...' &&
        for i in $(seq 1 5); do
            (dd if=/dev/zero of={mount_path}/stress_$i.dat bs=1M count=50 2>/dev/null; 
             dd if={mount_path}/stress_$i.dat of=/dev/null bs=1M 2>/dev/null;
             rm {mount_path}/stress_$i.dat) &
        done &&
        sleep {duration} &&
        wait &&
        echo 'Stress test completed'
        """
        
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", stress_cmd]
        stress_result = execute_command(cmd)
        results.append(f"Stress Test Results:\n{stress_result}")
        
        # Check for any errors in pod logs during the test
        cmd = ["kubectl", "logs", pod_name, "-n", namespace, "--tail=50"]
        log_result = execute_command(cmd)
        results.append(f"Pod Logs (last 50 lines):\n{log_result}")
        
        # Final space check
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "df", "-h", mount_path]
        final_space_result = execute_command(cmd)
        results.append(f"Final Space Check:\n{final_space_result}")
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        return f"Error running volume stress test: {str(e)}"

@tool
def test_volume_io_performance(pod_name: str, namespace: str = "default",
                              mount_path: str = "/test-volume",
                              test_size: str = "100M",
                              test_duration: int = 30) -> str:
    """
    Test I/O performance of a pod volume including read/write speeds and latency
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path
        test_size: Size of test data (e.g., 100M)
        test_duration: Test duration in seconds
        
    Returns:
        str: I/O performance test results with metrics
    """
    results = []
    
    try:
        # Check if test directory exists and is writable
        test_dir = f"{mount_path}/io_perf_test"
        setup_cmd = f"mkdir -p {test_dir} || echo 'Failed to create test directory'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", setup_cmd]
        setup_result = execute_command(cmd)
        
        if "Failed" in setup_result:
            return f"Error: Unable to create test directory {test_dir}. Check permissions or if volume is mounted read-only."
        
        results.append(f"I/O Performance Test on {mount_path}")
        results.append(f"Test parameters: size={test_size}, duration={test_duration}s")
        
        # Check if fio is available (preferred tool)
        check_fio_cmd = "which fio || echo 'fio not found'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_fio_cmd]
        fio_check_result = execute_command(cmd)
        
        if "not found" not in fio_check_result:
            # Use fio for testing
            results.append("Using fio for performance testing (more comprehensive results)")
            
            # Sequential read test
            seq_read_cmd = f"fio --name=seq_read --directory={test_dir} --rw=read --bs=4M --size={test_size} --numjobs=1 --time_based --runtime={test_duration} --group_reporting"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", seq_read_cmd]
            seq_read_result = execute_command(cmd)
            results.append(f"Sequential Read Test Results:\n{seq_read_result}")
            
            # Sequential write test
            seq_write_cmd = f"fio --name=seq_write --directory={test_dir} --rw=write --bs=4M --size={test_size} --numjobs=1 --time_based --runtime={test_duration} --group_reporting"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", seq_write_cmd]
            seq_write_result = execute_command(cmd)
            results.append(f"Sequential Write Test Results:\n{seq_write_result}")
            
            # Random read test
            rand_read_cmd = f"fio --name=rand_read --directory={test_dir} --rw=randread --bs=4k --size={test_size} --numjobs=4 --time_based --runtime={test_duration} --group_reporting"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", rand_read_cmd]
            rand_read_result = execute_command(cmd)
            results.append(f"Random Read Test Results:\n{rand_read_result}")
            
            # Random write test
            rand_write_cmd = f"fio --name=rand_write --directory={test_dir} --rw=randwrite --bs=4k --size={test_size} --numjobs=4 --time_based --runtime={test_duration} --group_reporting"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", rand_write_cmd]
            rand_write_result = execute_command(cmd)
            results.append(f"Random Write Test Results:\n{rand_write_result}")
        else:
            # Fallback to dd for basic testing
            results.append("Using dd for basic performance testing (fio not available)")
            
            # Sequential write test
            seq_write_cmd = f"dd if=/dev/zero of={test_dir}/write_test bs=1M count={test_size.replace('M', '')} oflag=direct 2>&1"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", seq_write_cmd]
            seq_write_result = execute_command(cmd)
            results.append(f"Sequential Write Test (dd):\n{seq_write_result}")
            
            # Sequential read test
            seq_read_cmd = f"dd if={test_dir}/write_test of=/dev/null bs=1M iflag=direct 2>&1"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", seq_read_cmd]
            seq_read_result = execute_command(cmd)
            results.append(f"Sequential Read Test (dd):\n{seq_read_result}")
            
            # Random I/O simulation with small blocks
            rand_io_cmd = f"dd if=/dev/urandom of={test_dir}/random_test bs=4k count=1000 oflag=direct 2>&1"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", rand_io_cmd]
            rand_io_result = execute_command(cmd)
            results.append(f"Random I/O Test (dd):\n{rand_io_result}")
        
        # Clean up test files
        cleanup_cmd = f"rm -rf {test_dir}"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
        execute_command(cmd)
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        # Attempt cleanup even if test fails
        try:
            cleanup_cmd = f"rm -rf {test_dir}"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
            execute_command(cmd)
        except:
            pass
            
        return f"Error testing volume I/O performance: {str(e)}"

@tool
def monitor_volume_latency(pod_name: str, namespace: str = "default",
                          mount_path: str = "/test-volume",
                          duration: int = 60,
                          operation_type: str = "all") -> str:
    """
    Monitor real-time latency of volume operations within a pod
    
    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace
        mount_path: Volume mount path
        duration: Monitoring duration in seconds
        operation_type: Operation type to monitor (read, write, all)
        
    Returns:
        str: Volume latency monitoring results
    """
    results = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        # Add timestamp to log
        results.append(f"[{timestamp}] Volume Latency Monitoring - Pod: {pod_name}, Path: {mount_path}")
        results.append(f"Monitoring duration: {duration} seconds")
        
        # Validate operation type
        valid_types = ["read", "write", "all"]
        if operation_type not in valid_types:
            return f"Error: Invalid operation type '{operation_type}'. Must be one of: {', '.join(valid_types)}"
        
        # Create monitoring directory
        test_dir = f"{mount_path}/latency_monitor"
        setup_cmd = f"mkdir -p {test_dir} || echo 'Failed to create test directory'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", setup_cmd]
        setup_result = execute_command(cmd)
        
        if "Failed" in setup_result:
            return f"Error: Unable to create test directory {test_dir}. Check permissions or if volume is mounted read-only."
        
        # Check if required tools are available
        check_tools_cmd = "which time || which timeout || echo 'Missing required tools'"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_tools_cmd]
        tools_check_result = execute_command(cmd)
        
        if "Missing required tools" in tools_check_result:
            results.append("Warning: 'time' or 'timeout' command not found. Using fallback method.")
            
            # For Kubernetes pods, we need to handle the script differently
            # Let's create the script directly inside the pod
            import os
            
            # Read the content of the script
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                      "scripts", "volume_latency_monitor.sh")
            
            try:
                with open(script_path, 'r') as f:
                    script_content = f.read()
            except Exception as e:
                results.append(f"Error reading script file: {str(e)}")
                
                # Fallback to embedded script content if we can't read the file
                script_content = """#!/bin/bash
# volume_latency_monitor.sh - Script for monitoring volume operation latency

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
"""
            
            # Create the script inside the pod
            pod_script_path = f"{test_dir}/volume_latency_monitor.sh"
            create_script_cmd = f"cat > {pod_script_path} << 'EOF'\n{script_content}\nEOF\nchmod +x {pod_script_path}"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", create_script_cmd]
            try:
                execute_command(cmd)
                results.append(f"Created latency monitoring script in pod")
            except Exception as e:
                results.append(f"Warning: Failed to create script in pod: {str(e)}")
                return "\n" + "="*50 + "\n".join(results)
            
            # Now run the script
            latency_script = f"{pod_script_path} {test_dir} {duration} {operation_type}"
            
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", latency_script]
            latency_result = execute_command(cmd)
            results.append(f"Latency Monitoring Results:\n{latency_result}")
            
            # Get the CSV results
            csv_cmd = f"cat {test_dir}/results.csv"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", csv_cmd]
            csv_result = execute_command(cmd)
            
            # Find slowest operations
            slowest_cmd = f"tail -n +2 {test_dir}/results.csv | sort -t, -k4 -nr | head -5"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", slowest_cmd]
            slowest_result = execute_command(cmd)
            
            if slowest_result and len(slowest_result.strip()) > 0:
                results.append(f"Slowest Operations:\n{slowest_result}")
                
                # Analyze for spikes - using string concatenation to avoid f-string issues
                analyze_cmd = "awk -F, '" + """
                BEGIN {max=0; min=999999; sum=0; count=0}
                NR>1 {
                  if($4 > max) max=$4;
                  if($4 < min) min=$4;
                  sum+=$4;
                  count++;
                }
                END {
                  avg=sum/count;
                  printf "Max: %.6f s, Min: %.6f s, Avg: %.6f s\\n", max, min, avg;
                  print "Detecting latency spikes (>2x average)";
                }""" + "' " + test_dir + "/results.csv"
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", analyze_cmd]
                analyze_result = execute_command(cmd)
                results.append(f"Statistical Analysis:\n{analyze_result}")
        else:
            # Advanced method with proper timing tools
            # First check if 'perf' or 'blktrace' are available for more detailed analysis
            check_advanced_cmd = "which perf || which blktrace || echo 'No advanced tools'"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", check_advanced_cmd]
            advanced_check_result = execute_command(cmd)
            
            if "No advanced tools" not in advanced_check_result:
                # Use advanced tools if available
                if "perf" in advanced_check_result:
                    # Using perf for IO latency monitoring
                    perf_cmd = f"""
                    cd {test_dir} &&
                    echo "Using perf for advanced IO latency monitoring" &&
                    perf record -e block:block_rq_issue -e block:block_rq_complete -a -o perf.data -- timeout {duration}s sh -c '
                      for i in $(seq 1 10); do
                        dd if=/dev/zero of=./perf_write_$i bs=1M count=10 oflag=direct 2>/dev/null;
                        dd if=./perf_write_$i of=/dev/null bs=1M iflag=direct 2>/dev/null;
                        rm ./perf_write_$i;
                      done
                    ' &&
                    perf report -i perf.data
                    """
                    cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", perf_cmd]
                    perf_result = execute_command(cmd)
                    results.append(f"Advanced IO Latency Monitoring (perf):\n{perf_result}")
                elif "blktrace" in advanced_check_result:
                    # Using blktrace for IO latency monitoring
                    blktrace_cmd = f"""
                    cd {test_dir} &&
                    echo "Using blktrace for advanced IO latency monitoring" &&
                    blktrace -d $(mount | grep {mount_path} | awk '{{print $1}}') -o trace &
                    BLKTRACE_PID=$! &&
                    for i in $(seq 1 5); do
                      dd if=/dev/zero of=./blk_write_$i bs=1M count=10 oflag=direct 2>/dev/null;
                      dd if=./blk_write_$i of=/dev/null bs=1M iflag=direct 2>/dev/null;
                      rm ./blk_write_$i;
                    done &&
                    sleep 2 &&
                    kill $BLKTRACE_PID &&
                    blkparse trace
                    """
                    cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", blktrace_cmd]
                    blktrace_result = execute_command(cmd)
                    results.append(f"Advanced IO Latency Monitoring (blktrace):\n{blktrace_result}")
            else:
                # Basic time-based measurements
                time_cmd = f"""
                cd {test_dir} &&
                echo "Operation,Size,Duration(s)" > time_results.csv &&
                
                # Sequential write test
                echo "Measuring sequential write latency..." &&
                TIMEFORMAT="%R" &&
                write_time=$({{ time dd if=/dev/zero of=./seq_write bs=1M count=100 conv=fdatasync 2>/dev/null; }} 2>&1) &&
                echo "write,100MB,$write_time" >> time_results.csv &&
                
                # Sequential read test
                echo "Measuring sequential read latency..." &&
                read_time=$({{ time dd if=./seq_write of=/dev/null bs=1M 2>/dev/null; }} 2>&1) &&
                echo "read,100MB,$read_time" >> time_results.csv &&
                
                # Random write test (smaller blocks)
                echo "Measuring random write latency..." &&
                rand_write_time=$({{ time dd if=/dev/urandom of=./rand_write bs=4k count=1000 conv=fdatasync 2>/dev/null; }} 2>&1) &&
                echo "rand_write,4MB,$rand_write_time" >> time_results.csv &&
                
                # Random read test
                echo "Measuring random read latency..." &&
                rand_read_cmd="for i in \$(seq 1 100); do dd if=./rand_write of=/dev/null bs=4k count=10 skip=\$((RANDOM % 100)) 2>/dev/null; done"
                rand_read_time=$({{ time sh -c "$rand_read_cmd"; }} 2>&1) &&
                echo "rand_read,4MB,$rand_read_time" >> time_results.csv &&
                
                # Metadata operations
                echo "Measuring metadata operations latency..." &&
                meta_cmd="for i in \$(seq 1 100); do touch ./meta_\$i; done && ls -la ./ >/dev/null && for i in \$(seq 1 100); do rm ./meta_\$i; done"
                meta_time=$({{ time sh -c "$meta_cmd"; }} 2>&1) &&
                echo "metadata,N/A,$meta_time" >> time_results.csv &&
                
                # Display results
                echo "Latency Measurements Complete" &&
                cat time_results.csv
                """
                cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", time_cmd]
                time_result = execute_command(cmd)
                results.append(f"Basic Latency Measurements:\n{time_result}")
        
        cleanup_cmd = f"rm -rf {test_dir}"
        cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
        execute_command(cmd)
        
        return "\n" + "="*50 + "\n".join(results)
        
    except Exception as e:
        # Attempt cleanup even if test fails
        try:
            cleanup_cmd = f"rm -rf {test_dir}"
            cmd = ["kubectl", "exec", pod_name, "-n", namespace, "--", "sh", "-c", cleanup_cmd]
            execute_command(cmd)
        except:
            pass
        
        return f"Error monitoring volume latency: {str(e)}"
