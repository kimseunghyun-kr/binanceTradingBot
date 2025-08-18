#!/bin/bash
set -e

echo "=== MongoDB Replica Set Initialization ==="

# Function to wait for MongoDB
wait_for_mongo() {
    local host=$1
    echo "Waiting for $host to be ready..."
    while ! mongosh --host "$host" --quiet --eval "db.adminCommand('ping')" >/dev/null 2>&1; do
        echo "  Still waiting for $host..."
        sleep 3
    done
    echo "  $host is ready!"
}

# Wait for both MongoDB instances
wait_for_mongo "mongo1:27017"
wait_for_mongo "mongo2:27017"

echo "Configuring replica set..."

# Try to initialize replica set
mongosh --host mongo1:27017 --eval "
try {
    rs.status();
    print('Replica set already configured');
} catch (e) {
    print('Initializing replica set...');
    rs.initiate({
        _id: 'rs0',
        members: [
            { _id: 0, host: 'mongo1:27017' },
            { _id: 1, host: 'mongo2:27017' }
        ]
    });
    
    // Wait for primary
    var attempts = 0;
    while (attempts < 30) {
        try {
            var status = rs.status();
            if (status.members.some(m => m.stateStr === 'PRIMARY')) {
                print('Primary is ready!');
                break;
            }
        } catch (e) {
            // ignore
        }
        print('Waiting for primary... attempt ' + (attempts + 1));
        sleep(1000);
        attempts++;
    }
}
"

echo "=== MongoDB initialization completed ==="
