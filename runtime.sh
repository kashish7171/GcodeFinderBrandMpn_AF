#!/bin/bash

# Ensure that the virtual environment is activated (if you're using one)
source /root/chrome-env/bin/activate

# name of the project
PORJECT_NAME="AF GCODE Finder"

# Path to your log directory and the log file
LOG_DIR="/root/public/GcodeFinderBrandMpn(AF)/logs"
LOG_FILE="$LOG_DIR/google.scrapper.module.log"

# Reboot log file
REBOOT_LOG_FILE="/root/reboot_log.txt"

# Function to check if the scraper process is running
check_process() {
    pgrep -f "python3 googleShoppingBot.py" > /dev/null
    return $?
}

# Function to check if the process is stuck (i.e., not progressing)
check_if_stuck() {
    # Check if the process is running but has been running for too long (e.g., more than 3 minutes)
    stuck_process=$(ps -eo pid,etime,comm | grep "python3 googleShoppingBot.py" | grep -v grep)
    
    if [ -n "$stuck_process" ]; then
        # Extract the elapsed time of the process
        elapsed_time=$(echo $stuck_process | awk '{print $2}')
        
        # Convert elapsed time to minutes (this is a simple approach, you may need a more complex one)
        if [[ "$elapsed_time" =~ [0-9]+:[0-9]+ ]]; then
            # Check if the elapsed time is over 3 minutes
            minutes=$(echo $elapsed_time | cut -d ":" -f1)
            if [ "$minutes" -gt 3 ]; then
                return 0  # Process is stuck
            fi
        fi
    fi
    
    return 1  # Process is not stuck
}

# Function to check if log file was modified in the last 30 minutes
check_log_last_modified() {
    # Get the last modified time of the log file in seconds
    last_modified=$(stat -c %Y "$LOG_FILE")
    
    # Get the current time in seconds
    current_time=$(date +%s)
    
    # Calculate the difference in seconds
    let time_diff=current_time-last_modified
    
    # Debugging output to see the values
    # echo "Last modified time (Unix timestamp): $last_modified"
    # echo "Current time (Unix timestamp): $current_time"
    # echo "Time difference (in seconds): $time_diff"

    # Return the time difference
    echo $time_diff
}

# Function to delete the log directory
delete_log_directory() {
    if [ -d "$LOG_DIR" ]; then
        echo "Deleting log directory..."
        rm -rf "$LOG_DIR"  # This will remove the directory and all its contents
    fi
}

# Function to log a reboot action to the log file
log_reboot() {
    # Check if log file exists, if not, create it
    if [ ! -f "$REBOOT_LOG_FILE" ]; then
        touch "$REBOOT_LOG_FILE"
    fi
    
    # Log the reboot with the current timestamp
    echo "$(date '+%d %b, %Y %H:%M:%S') - Rebooted" >> "$REBOOT_LOG_FILE"
}

# start the process
start_process() {
    cd '/root/public/GcodeFinderBrandMpn(AF)/' && python3 googleShoppingBot.py &
    echo "$PORJECT_NAME started."
}

# Run the scraping process if it's not already running
if ! check_process; then
    echo "$PORJECT_NAME is not running. Starting..."
    start_process

    # Wait for 3 minutes before entering the check loop
    sleep 180

    # Start the loop to monitor the process every minute
    while true; do
        # Check if the scraping process is still running
        if ! check_process; then
            echo "$PORJECT_NAME is not running. Checking if it is stuck..."

            # Check if the process is stuck
            if check_if_stuck; then
                echo "Process seems stuck. Waiting for 3 minutes before re-checking..."
                sleep 180  # Wait for 3 minutes before checking again

                # Recheck if the process is still stuck after waiting
                if check_if_stuck; then
                    echo "Process is still stuck after waiting 3 minutes. Rebooting the server..."
                    log_reboot  # Log the reboot action
                    sudo reboot
                else
                    # If the process is no longer stuck
                    echo "$PORJECT_NAME seems fine after waiting 3 minutes..."
                fi
            else
                # If the process finished normally, start the scraper again
                echo "Process finished. Restarting the process..."
                start_process
            fi
        else
            echo "$PORJECT_NAME is still running."

            # Get the time difference since the log file was last modified
            time_diff=$(check_log_last_modified)
            echo "Last modified time: $time_diff"

            # If the time difference is greater than 1800 seconds (30 minutes), the file has not been updated recently
            if [ "$time_diff" -gt 1800 ]; then
                echo "Log files hasn't been updated in the last 30 minutes. Deleting log directory and rebooting the server..."
                delete_log_directory  # Delete the log directory
                log_reboot  # Log the reboot action
                sudo reboot
            fi
        fi

        # Wait for 60 seconds before checking again
        sleep 60
    done
else
    echo "$PORJECT_NAME is already running."
    
    # Get the time difference since the log file was last modified
    time_diff=$(check_log_last_modified)
    echo "Last modified time: $time_diff"

    # If the time difference is greater than 1800 seconds (30 minutes), the file has not been updated recently
    if [ "$time_diff" -gt 1800 ]; then
        echo "Log files hasn't been updated in the last 30 minutes. Deleting log directory and rebooting the server..."
        delete_log_directory  # Delete the log directory
        log_reboot  # Log the reboot action
        sudo reboot
    fi
fi
