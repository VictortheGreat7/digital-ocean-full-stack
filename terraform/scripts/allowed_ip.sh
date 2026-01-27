#!/usr/bin/env bash

set -eu

SSH_KEYS_DIR="../ssh_keys"
VARIABLES_FILE="../variables.tf"

# Check if ssh_keys directory exists
if [ ! -d "$SSH_KEYS_DIR" ]; then
    echo "Error: $SSH_KEYS_DIR directory not found"
    exit 1
fi

# Import each public key to DigitalOcean
for key_file in "$SSH_KEYS_DIR"/*.pub; do
    if [ -f "$key_file" ]; then
        key_name=$(basename "$key_file" .pub)
        echo "Importing $key_name..."
        
        key_id=$(doctl compute ssh-key import "$key_name" --public-key-file "$key_file" --format ID --no-header)
        echo "Imported $key_name with ID: $key_id"
        
        # Update variables.tf - append key_id to the default list
        if grep -q "default.*= \[\]" "$VARIABLES_FILE"; then
            # List is empty, add without comma
            sed -i "/variable \"ssh_key_ids\"/,/^}/s/default.*= \[\]/default     = [$key_id]/" "$VARIABLES_FILE"
        else
            # List has contents, add with comma
            sed -i "/variable \"ssh_key_ids\"/,/^}/s/\]/, $key_id]/" "$VARIABLES_FILE"
        fi
    fi
done

echo "All SSH keys imported successfully"