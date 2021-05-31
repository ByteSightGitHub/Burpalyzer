Parameters are (in order)
botname: Twitch username of the bot
prefix = Chat text the bot uses for the rating
indir = Folder with the raw chat logs
excludefile = File with IDs that will be excluded from the statistics
outdir = Folder where output files will be stored

Example command line usage:
	mkdir output
	python ChatParser.py beaburpbot "Time's up! Final rating is: " c:\PATH\TO\\rawlogs_2020-05 exclude_list_beaburpbot.txt output
