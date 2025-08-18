#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for mongo1 and mongo2..."

# Wait for mongo1
echo "Connecting to mongo1..."
until mongosh --host mongo1:27017 --quiet --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q 1; do 
    echo "Waiting for mongo1..."
    sleep 2
done
echo "mongo1 is ready!"

# Wait for mongo2  
echo "Connecting to mongo2..."
until mongosh --host mongo2:27017 --quiet --eval 'db.adminCommand("ping").ok' 2>/dev/null | grep -q 1; do 
    echo "Waiting for mongo2..."
    sleep 2
done
echo "mongo2 is ready!"

echo "Initiating replica set if needed..."
mongosh --host mongo1:27017 --quiet <<'JS'
const cfg = {
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017" },
    { _id: 1, host: "mongo2:27017" }
  ]
};
try {
  const s = rs.status();
  if (s.ok === 1) {
    print("Replica set already configured.");
  }
} catch (e) {
  if (String(e).match(/not yet initialized|no replset config/)) {
    rs.initiate(cfg);
  } else {
    print(e);
  }
}
let tries = 60;
while (tries-- > 0) {
  const s = rs.status();
  if (s.ok === 1 && s.members && s.members.some(m => m.stateStr === "PRIMARY")) {
    print("PRIMARY ready.");
    break;
  }
  sleep(1000);
}
JS
