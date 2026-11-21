#!/usr/bin/env bash
set -euo pipefail
PROJECT="$HOME/projects/YeAH-TCP-NPE"
NS3="$HOME/projects/ns-3.44"
OUT="$PROJECT/results/raw/validation/g4"
if [[ -e "$OUT" ]]; then
    echo "G4 output already exists; preserve it and request recovery instructions."
    exit 1
fi
cd "$NS3"
[[ "$(git rev-parse HEAD)" == 43dce6710b8df69685e3479c1d33a571dda714ea ]]
git diff --quiet HEAD -- src
[[ "$(sha256sum "$PROJECT/simulation/yeah-experiment.cc" | cut -d' ' -f1)" == 460600eea2ba2341df49a284022ebd678d1d32adad5b695b8de93c97c1ff5969 ]]
mkdir -p "$OUT"/{yeah60,reno60,loss50}
cp "$PROJECT/simulation/yeah-experiment.cc" scratch/yeah-experiment.cc
{
    cat VERSION
    git rev-parse HEAD
    git status --short
    git diff HEAD -- src
    sha256sum scratch/yeah-experiment.cc
    nproc
    free -h
    df -h .
} > "$OUT/environment.log"
./ns3 configure --build-profile=optimized --out=build/optimized \
    --enable-examples --enable-tests \
    --enable-modules='core;network;internet;point-to-point;applications;traffic-control;flow-monitor' \
    2>&1 | tee "$OUT/configure.log"
{ time cmake --build cmake-cache -j 4 --target scratch_yeah-experiment; } 2>&1 | tee "$OUT/build.log"
{
    echo '=== CMAKE PROFILE ==='
    grep -E '^(CMAKE_BUILD_TYPE|NS3_ASSERT|NS3_LOG|NS3_NATIVE_OPTIMIZATIONS|NS3_OUTPUT_DIRECTORY):' cmake-cache/CMakeCache.txt || true
    echo '=== EXECUTABLE ==='
    find build/optimized/scratch -maxdepth 1 -type f -name '*yeah-experiment*' -print -exec sha256sum {} \;
} >> "$OUT/environment.log"
for TCP in yeah reno; do
    echo "=== G4: ${TCP}60 ==="
    { time ./ns3 run "scratch/yeah-experiment --tcp1=$TCP --tcp2=$TCP --flows=2 --capacity=500 --rtt1=80 --rtt2=80 --bufferRatio=1 --duration=60 --loss=0 --flow2Start=0 --flow2Stop=60 --seed=1 --run=1 --mss=1448 --initialCwnd=10 --initialSsthreshSegments=0 --out=$OUT/${TCP}60" --no-build; } 2>&1 | tee "$OUT/${TCP}60/run.log"
done
{ time ./ns3 run "scratch/yeah-experiment --tcp1=yeah --tcp2=yeah --capacity=50 --rtt1=80 --rtt2=80 --duration=20 --loss=0.001 --seed=1 --run=1 --out=$OUT/loss50" --no-build; } 2>&1 | tee "$OUT/loss50/run.log"
cd "$PROJECT"
tar -czf "$HOME/projects/step-G4-optimized.tar.gz" results/raw/validation/g4 simulation/yeah-experiment.cc scripts/run_G4_optimized.sh
printf '\n=== G4 COMPLETE ===\n'
ls -lh "$HOME/projects/step-G4-optimized.tar.gz"
