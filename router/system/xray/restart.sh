#!/system/bin/busybox ash
DIR=/system/xray
"$DIR/stop.sh"
"$DIR/gen_config.sh"
"$DIR/start.sh"
