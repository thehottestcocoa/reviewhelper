#!/bin/bash
# cron에 등록해서 2-3일마다 실행
# crontab -e 에서 아래처럼 등록 (월·목 오전 9시):
#   0 9 * * 1,4 /Users/han-yeeun/Desktop/reviewhelper/run.sh

cd "$(dirname "$0")"
/Library/Developer/CommandLineTools/usr/bin/python3 main.py >> logs/run.log 2>&1
