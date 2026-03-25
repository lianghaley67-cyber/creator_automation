@echo off
powershell -ExecutionPolicy Bypass -File "C:\Users\HP\Documents\Playground\creator_automation\run_videohao_daily.ps1" -InputCsv "C:\Users\HP\Documents\Playground\creator_automation\data\videohao_posts.csv" -Days 3 -Mock
