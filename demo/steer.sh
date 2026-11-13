#!/usr/bin/env bash
# Just the steering-button window (Tk). Attach it to an already running simulation,
# e.g. after ./spin.sh or ./explore.sh. Buttons publish to /cmd_vel.
# (During ./explore.sh the explorer drives; steering there will fight it.)
source "$(dirname "$0")/common.sh"
exec bash "$NAV/steer_gui.sh"
