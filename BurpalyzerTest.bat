@ECHO OFF
mkdir output
python burpalyzer_main.py beaburpbot %HOMEDRIVE%%HOMEPATH%\Desktop\twitch-chat-download\rawlogs fixup_list_beaburpbot.txt output
