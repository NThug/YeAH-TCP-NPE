#!/usr/bin/env bash
set -euo pipefail
project="$(cd "$(dirname "$0")/.." && pwd)"
ns3="${NS3_DIR:-$HOME/projects/ns-3.44}"
result="$project/results/raw/pilot"
mkdir -p "$result"
cp "$project/simulation/yeah-experiment.cc" "$ns3/scratch/yeah-experiment.cc"
cd "$ns3"
# Capture build and pilot logs; do not continue on failed command.
run_case() {
    local id="$1"; shift
    mkdir -p "$result/$id"
    echo "=== $id ==="
    { time ./ns3 run "scratch/yeah-experiment $* --out=$result/$id"; } 2>&1 | tee "$result/$id/run.log"
}
run_case yeah50 --tcp1=yeah --tcp2=yeah --capacity=50 --rtt1=80 --rtt2=80 --duration=20
run_case reno50 --tcp1=reno --tcp2=reno --capacity=50 --rtt1=80 --rtt2=80 --duration=20
run_case yeah500 --tcp1=yeah --tcp2=yeah --capacity=500 --rtt1=80 --rtt2=80 --duration=15
cd "$project"
tar -czf "$HOME/projects/step-F-pilot.tar.gz" results/raw/pilot simulation/yeah-experiment.cc
printf '\nCreated %s\n' "$HOME/projects/step-F-pilot.tar.gz"
