Parameters are (in order)
botname: Twitch username of the bot
indir = Folder with the raw chat logs
fixup_file = File with instructions on invalid burps or manually specified twitch clips
outdir = Folder where output files will be stored

Example command line usage:
	mkdir output
	python burpalyzer_main.py  beaburpbot c:\PATH\TO\\rawlogs_2020-05 fixup_list_beaburpbot.txt output
