#!/bin/sh
set -e

# Default action from environment variable or argument
ACTION="${RELEASE_ACTION:-generate-version}"

# Build command arguments
CMD="/app/release.py $ACTION"

# Add config file if specified
if [ -n "$CONFIG_FILE" ]; then
    CMD="$CMD --config $CONFIG_FILE"
fi

# Add dry run flag if enabled
if [ "$DRY_RUN" = "true" ]; then
    CMD="$CMD --dry-run"
fi

# Add output file if specified
if [ -n "$OUTPUT_FILE" ]; then
    CMD="$CMD --output $OUTPUT_FILE"
fi

# Add platform if specified
if [ -n "$PLATFORM" ]; then
    CMD="$CMD --platform $PLATFORM"
fi

# Execute the release script
exec python3 $CMD "$@"
