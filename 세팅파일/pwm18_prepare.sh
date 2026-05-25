#!/bin/bash
set -e

CHIP="/sys/class/pwm/pwmchip0"
CH="2"
PWM="$CHIP/pwm$CH"

[ -d "$CHIP" ] || { echo "No $CHIP"; exit 1; }

[ -d "$PWM" ] || echo "$CH" > "$CHIP/export"
sleep 0.2

echo 20000000 > "$PWM/period"
echo 1500000  > "$PWM/duty_cycle"
echo 0        > "$PWM/enable"

chown pi:pi "$PWM/period" "$PWM/duty_cycle" "$PWM/enable"
chmod 660    "$PWM/period" "$PWM/duty_cycle" "$PWM/enable"

echo "$PWM" > /run/pwm18_path
chown pi:pi /run/pwm18_path

echo "PWM18 ready: $PWM"
