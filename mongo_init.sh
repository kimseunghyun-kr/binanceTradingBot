#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for mongo1 and mongo2..."
until mongosh --host mongo1:27017 --quiet --eval 'db.adminCommand("ping").ok' | grep 1 >/dev/null; do sleep 1; done
until mongosh --host mongo2:27017 --quiet --eval 'db.adminCommand("ping").ok' | grep 1 >/dev/null; do sleep 1; done

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
