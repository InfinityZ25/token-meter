#!/bin/bash

user="InfinityZ25"
limit=1000
retention_days=182

# Function to calculate days between two dates
days_between() {
    local start_date="$1"
    local end_date=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local seconds=$(($(date -d "$end_date" +%s) - $(date -d "$start_date" +%s)))
    echo $((seconds / 86400))
}

echo "Starting script with user=$user, limit=$limit, retention_days=$retention_days"

# Fetch repos and process each one
gh repo list "$user" -L "$limit" --json name,pushedAt,isPrivate | jq -c '.[]' | while read -r repo; do
    name=$(echo "$repo" | jq -r '.name')
    pushed_at=$(echo "$repo" | jq -r '.pushedAt')
    is_private=$(echo "$repo" | jq -r '.isPrivate')

    echo "--------------------------------------------------"
    echo "RepoName: $name"
    echo "Last pushed at: $pushed_at"
    echo "Is Private: $is_private"

    days_diff=$(days_between "$pushed_at")

    echo "Days since last push: $days_diff"

    if [ "$days_diff" -gt "$retention_days" ] && [ "$is_private" = "false" ]; then
        echo "$name is older than $retention_days days ($days_diff days) and is public"
        echo "Attempting to change visibility to private..."
        if gh repo edit "$user/$name" --visibility private; then
            echo "Successfully changed visibility to private."
            echo "Attempting to archive the repository..."
            if gh repo archive "$user/$name" -y; then
                echo "Successfully archived $name."
            else
                echo "Failed to archive $name. Please check permissions and try again."
            fi
        else
            echo "Failed to change visibility of $name. Please check permissions and try again."
        fi
    elif [ "$days_diff" -gt "$retention_days" ] && [ "$is_private" = "true" ]; then
        echo "$name is older than $retention_days days ($days_diff days) and is already private"
        echo "Attempting to archive the repository..."
        if gh repo archive "$user/$name" -y; then
            echo "Successfully archived $name."
        else
            echo "Failed to archive $name. Please check permissions and try again."
        fi
    else
        echo "$name is not old enough to archive (only $days_diff days old) or is already private"
    fi
done

echo "Script completed."
