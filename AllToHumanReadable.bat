@ECHO OFF
mkdir output\human_readable
pushd venv
CALL Scripts\activate.bat
popd
py -3 to_human_readable.py %HOMEDRIVE%%HOMEPATH%\Desktop\twitch-chat-download\rawlogs output\human_readable
