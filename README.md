# soccer-prediction

### poisson.py

code for https://steemit.com/python/@stevencurrie/soccer-predictions-using-python-part-1 & https://steemit.com/programming/@stevencurrie/soccer-predictions-using-python-part-2


### soccerprediction.py

updated code for https://steemit.com/programming/@stevencurrie/soccer-predictions-using-python-part-3

updated code for https://steemit.com/programming/@stevencurrie/soccer-predictions-using-python-part-4

updated code for https://steemit.com/programming/@stevencurrie/soccer-predictions-using-python-part-5


Successfully tested on standard windows installation of python 3.6.

copied soccerprediction.py to it's own folder.

to install dependencies run 
```
pip install pandas
pip install requests
pip install beautifulsoup4
```

then run
```
python soccerprediction.py -t
```
This will download data for the English Premier League (default -c "England" -l "Premier League") and run tests on the data to find the best settings for the -y <HISTORY> and -b <CUTOFF> options.
  
At this time, it returns 400 for HISTORY and 70 for cutoff.
```
python soccerprediction.py -y 400 -b 70
```
will run the prediction and printout to the console any games that include a probability higher than the cutoff of 70%.

You can add the -d YYY-MM-DD option to predict a few days in advance.  Not recommended to go to far as this would decrease the accuracy.
```
python soccerprediction.py -y 400 -b 70 -d 2017-09-30
```

Currently only checking to Home/Draw/Away - If you want to add checks for over/under, both to score etc, feel free.
A spreadsheet (.CSV) is saved for each competition in the data folder in the same location as soccerprediction.py


