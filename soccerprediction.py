#!/usr/bin/python3
import argparse
import datetime
from os import path, makedirs

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs


def scrapeseason(country, comp, season):
    # output what the function is attempting to do.
    print("Scraping:", country, comp, str(season) + "-" + str(season + 1))
    baseurl = "http://www.soccerpunter.com/soccer-statistics/"
    scrapeaddress = (baseurl + country + "/" + comp.replace(" ", "-").replace("/", "-") + "-"
                     + str(season) + "-" + str(season + 1) + "/results")
    print("URL:", scrapeaddress)
    print("")

    # scrape the page and create beautifulsoup object
    content = requests.get(scrapeaddress).text
    page = bs(content, "html.parser")

    # find the main data table within the page source
    maintable = page.find("table", "competitionRanking")

    # seperate the data table into rows
    games = maintable.find_all("tr")

    # create an empty pandas dataframe to store our data
    df = pd.DataFrame(columns=["date", "homeTeam", "homeScore", "awayScore", "awayTeam"])

    idx = 0
    today = datetime.date.today()

    for game in games:

        # these lines filter out any rows not containing game data, some competitions contain extra info.
        try:
            cls = game["class"]
        except:
            cls = "none"
        if ("titleSpace" not in cls and "compHeading" not in cls and
                    "matchEvents" not in cls and "compSubTitle" not in cls and cls != "none"):

            datestr = game.find("a").text
            gamedate = datetime.datetime.strptime(datestr, "%d/%m/%Y").date()

            # filter out "extra time", "penalty shootout" and "neutral ground" markers
            hometeam = game.find("td", "teamHome").text
            hometeam = hometeam.replace("[ET]", "").replace("[PS]", "").replace("[N]", "").strip()
            awayteam = game.find("td", "teamAway").text
            awayteam = awayteam.replace("[ET]", "").replace("[PS]", "").replace("[N]", "").strip()

            # if game was played before today, try and get the score
            if gamedate < today:
                scorestr = game.find("td", "score").text

                # if the string holding the scores doesn't contain " - " then it hasn't yet been updated
                if " - " in scorestr:
                    homescore, awayscore = scorestr.split(" - ")

                    # make sure the game wasn't cancelled postponed or suspended
                    if homescore != "C" and homescore != "P" and homescore != "S":
                        # store game in dataframe
                        df.loc[idx] = {"date": gamedate.strftime("%Y-%m-%d"),
                                       "homeTeam": hometeam,
                                       "homeScore": int(homescore),
                                       "awayScore": int(awayscore),
                                       "awayTeam": awayteam}
                        # update our index
                        idx += 1
            else:
                # it's a future game, so store it with scores of -1
                df.loc[idx] = {"date": gamedate.strftime("%Y-%m-%d"),
                               "homeTeam": hometeam,
                               "homeScore": -1,
                               "awayScore": -1,
                               "awayTeam": awayteam}
                idx += 1

    # sort our dataframe by date
    df.sort_values(['date', 'homeTeam'], ascending=[True, True], inplace=True)
    df.reset_index(inplace=True, drop=True)
    # add a column containing the season, it'll come in handy later.
    df["season"] = season
    return df


def getcompetitiondata(country, comp, startseason, datapath):
    # make sure our datapath exists
    if not path.exists(datapath):
        makedirs(datapath)
    # set a filename for our data
    filename = datapath + country + "-" + comp.replace(" ", "-").replace("/", "-") + ".csv"

    if not path.isfile(filename):
        seasondata = []
        currentseason = datetime.date.today().year

        # scrape each season
        for s in range(startseason, currentseason + 1):
            seasondata.append(scrapeseason(country, competition, s))

        # combine our data to one frame
        data = pd.concat(seasondata)
        data.reset_index(inplace=True, drop=True)

        # save to file so we don't need to scrape multiple times
        data.to_csv(filename)
    else:
        # load our csv
        data = pd.read_csv(filename, index_col=0, parse_dates=True)

    return data


def updatecompetitiondata(country, comp, startseason, datapath):
    filename = datapath + country + "-" + comp.replace(" ", "-").replace("/", "-") + ".csv"
    currentseason = datetime.date.today().year
    todaysdate = datetime.date.today().strftime("%Y-%m-%d")

    # load (or scrape) our current data
    currentdata = getcompetitiondata(country, comp, startseason, datapath)

    # scrape the latest data for this competition
    latestdata = scrapeseason(country, comp, currentseason)

    # get index of games that we want to update - homescore will be -1 and date will be today or earlier
    updateneeded = currentdata.loc[currentdata["homeScore"] < 0].loc[currentdata["date"] <= todaysdate].index.values

    # for each game in the index
    for i in updateneeded:
        # get the date and hometeam
        gamedate = currentdata.ix[i, "date"]
        hometeam = currentdata.ix[i, "homeTeam"]

        # find same date and hometeam in the update dataframe and get the home & away scores
        homescore = latestdata.loc[latestdata["date"] == gamedate].loc[latestdata["homeTeam"] == hometeam, "homeScore"]
        awayscore = latestdata.loc[latestdata["date"] == gamedate].loc[latestdata["homeTeam"] == hometeam, "awayScore"]

        # store the updated scores in our currentdata
        currentdata.ix[i, "homeScore"] = homescore.values[0]
        currentdata.ix[i, "awayScore"] = awayscore.values[0]

    # save to file
    currentdata.to_csv(filename)
    return currentdata


def poissonpredict(df, gamedate, historylength, cutoff=-1):
    # set the amount of simulations to run on each game
    simulatedgames = 100000

    # only use games before the date we want to predict
    historical = df.loc[df["date"] < gamedate]

    # make sure we only use games that have valid scores
    historical = historical.loc[df["homeScore"] > -1]

    # limit historical data to set length
    historical = historical.tail(historylength)

    # games to predict
    topredict = df.loc[df["date"] == gamedate]

    # get average home and away scores for entire competition
    homeAvg = historical["homeScore"].mean()
    awayAvg = historical["awayScore"].mean()

    # loop through the games we want to predict
    for i in topredict.index:
        ht = topredict.ix[i, "homeTeam"]
        at = topredict.ix[i, "awayTeam"]

        # get average goals scored and conceded for home team
        homeTeamHomeAvgFor = historical.loc[df["homeTeam"] == ht, "homeScore"].mean()
        homeTeamHomeAvgAgainst = historical.loc[df["homeTeam"] == ht, "awayScore"].mean()

        # divide averages for team by averages for competition to get attack and defence strengths
        homeTeamAttackStrength = homeTeamHomeAvgFor / homeAvg
        homeTeamDefenceStrength = homeTeamHomeAvgAgainst / awayAvg

        # repeat for away team
        awayTeamAwayAvgFor = historical.loc[df["awayTeam"] == at, "awayScore"].mean()
        awayTeamAwayAvgAgainst = historical.loc[df["awayTeam"] == at, "homeScore"].mean()
        awayTeamAttackStrength = awayTeamAwayAvgFor / awayAvg
        awayTeamDefenceStrength = awayTeamAwayAvgAgainst / homeAvg

        # calculated expected goals using attackstrength * defencestrength * average
        homeTeamExpectedGoals = homeTeamAttackStrength * awayTeamDefenceStrength * homeAvg
        awayTeamExpectedGoals = awayTeamAttackStrength * homeTeamDefenceStrength * awayAvg

        # use numpy's poisson distribution to simulate 100000 games between the two teams
        homeTeamPoisson = np.random.poisson(homeTeamExpectedGoals, simulatedgames)
        awayTeamPoisson = np.random.poisson(awayTeamExpectedGoals, simulatedgames)

        # we can now infer some predictions from our simulated games
        # using numpy to count the results and converting to percentage probability
        homeTeamWins = np.sum(homeTeamPoisson > awayTeamPoisson) / simulatedgames * 100
        draws = np.sum(homeTeamPoisson == awayTeamPoisson) / simulatedgames * 100
        awayTeamWins = np.sum(homeTeamPoisson < awayTeamPoisson) / simulatedgames * 100
        totalGoals = np.mean(homeTeamPoisson + awayTeamPoisson)
        threeOrMoreGoals = np.sum((homeTeamPoisson + awayTeamPoisson) > 2) / simulatedgames * 100
        bothTeamsToScore = np.sum((homeTeamPoisson > 0) & (awayTeamPoisson > 0)) / simulatedgames * 100

        # store our prediction into the dataframe
        df.ix[i, "homeWin"] = homeTeamWins
        df.ix[i, "draw"] = draws
        df.ix[i, "awayWin"] = awayTeamWins
        df.ix[i, "totalGoals"] = totalGoals
        df.ix[i, "threeOrMoreGoals"] = threeOrMoreGoals
        df.ix[i, "bothTeamsToScore"] = bothTeamsToScore

        # if probability exceeds our cutoff, print out the game and the expected result
        if (draws > cutoff or homeTeamWins > cutoff or awayTeamWins > cutoff) and cutoff > 0:
            if draws > cutoff:
                result = "Draw"
                probability = draws
                odds = 100 / draws
            elif homeTeamWins > cutoff:
                result = ht + " Win"
                probability = homeTeamWins
                odds = 100 / homeTeamWins
            elif awayTeamWins > cutoff:
                result = at + " Win"
                probability = awayTeamWins
                odds = 100 / awayTeamWins
            print("{0} v {1} : Prediction:{2}, Probability:{3:.2f}, Odds:{4:.2f}".format(ht, at, result, probability,
                                                                                         odds))

    return df


def runtests(data, testdays=30):
    startdate = datetime.datetime.today() - datetime.timedelta(days=365)

    bestscore = 0
    besthistory = 0
    bestcutoff = 0
    gamespredicted = 0

    for cutoff in range(40, 95, 5):
        for history in range(25, 500, 25):
            correct = 0
            totalgames = 0
            possiblegames = 0
            gamedate = startdate
            for d in range(testdays):
                predictdate = gamedate.strftime("%Y-%m-%d")
                gameindex = data.loc[data["date"] == predictdate].index

                if gameindex.shape[0] > 0:
                    data = poissonpredict(data, predictdate, history)

                    for i in gameindex:
                        homescore = data.ix[i]["homeScore"]
                        awayscore = data.ix[i]["awayScore"]
                        homewin = data.ix[i]["homeWin"]
                        draw = data.ix[i]["draw"]
                        awaywin = data.ix[i]["awayWin"]

                        if homescore == awayscore and draw > homewin and draw > awaywin and draw >= cutoff:
                            correct += 1
                        if homescore > awayscore and homewin > draw and homewin > awaywin and homewin >= cutoff:
                            correct += 1
                        if awayscore > homescore and awaywin > draw and awaywin > homewin and awaywin >= cutoff:
                            correct += 1
                        if draw > cutoff or homewin > cutoff or awaywin > cutoff:
                            totalgames += 1
                        possiblegames += 1

                gamedate += datetime.timedelta(days=1)

            if totalgames > 0:
                score = correct / totalgames * 100
            else:
                score = 0

            if (score > bestscore or (
                            score == bestscore and totalgames > gamespredicted)) and totalgames >= possiblegames / 10:
                bestscore = score
                besthistory = history
                bestcutoff = cutoff
                gamespredicted = totalgames
                print("History:{0} Cutoff:{1:.2f} Score:{2:.2f}%".format(history, cutoff, score))
                print("{0}/{1} results predicted correctly from {2} possible games".format(correct, totalgames,
                                                                                           possiblegames))

    return besthistory, bestcutoff, bestscore


def confirmtests(data, history, cutoff, testdays=30):
    startdate = datetime.datetime.today() - datetime.timedelta(days=365 - testdays)

    correct = 0
    totalgames = 0
    possiblegames = 0
    gamedate = startdate
    for d in range(testdays):
        predictdate = gamedate.strftime("%Y-%m-%d")
        gameindex = data.loc[data["date"] == predictdate].index

        if gameindex.shape[0] > 0:
            data = poissonpredict(data, predictdate, history)

            for i in gameindex:
                homescore = data.ix[i]["homeScore"]
                awayscore = data.ix[i]["awayScore"]
                homewin = data.ix[i]["homeWin"]
                draw = data.ix[i]["draw"]
                awaywin = data.ix[i]["awayWin"]

                if homescore == awayscore and draw > homewin and draw > awaywin and draw >= cutoff:
                    correct += 1
                if homescore > awayscore and homewin > draw and homewin > awaywin and homewin >= cutoff:
                    correct += 1
                if awayscore > homescore and awaywin > draw and awaywin > homewin and awaywin >= cutoff:
                    correct += 1
                if draw > cutoff or homewin > cutoff or awaywin > cutoff:
                    totalgames += 1
                possiblegames += 1

        gamedate += datetime.timedelta(days=1)

    if totalgames > 0:
        score = correct / totalgames * 100
    else:
        score = 0

    return score


todaysdate = datetime.date.today().strftime("%Y-%m-%d")

# initialise parser object to read from command line
parser = argparse.ArgumentParser()

# add our required arguments
parser.add_argument("-u", "--update", action="store_true", help="Update with latest scores")
parser.add_argument("-c", "--country", default="England", help="Country to read data for")
parser.add_argument("-l", "--league", default="Premier League", help="Competition/League to read data for")
parser.add_argument("-d", "--date", default=todaysdate, help="Date of games to predict YYYY-MM-DD, eg 2017-09-20")
parser.add_argument("-p", "--path", default="data/", help="Path to store data files, relative to location of this file")
parser.add_argument("-y", "--history", default=100, type=int, help="Number of historical games to consider")
parser.add_argument("-t", "--test", action="store_true", help="Run tests to find best history length and cutoff values")
parser.add_argument("-b", "--cutoff", default=-1, type=int, help="Cutoff probability for betting")

# parse the arguments from the command line input and store them in the args variable
args = parser.parse_args()

# read from the args variable and store in more sensible vars
country = args.country
competition = args.league
gamedate = args.date
datapath = args.path
history = args.history
testmode = args.test
cutoff = args.cutoff

# if update requested then update, otherwise just use the existing data
if args.update:
    data = updatecompetitiondata(country, competition, 2014, datapath)
else:
    data = getcompetitiondata(country, competition, 2014, datapath)

if testmode:
    besthistory, bestcutoff, bestscore = runtests(data, testdays=60)
    print("Score of {0:.2f}% with history setting of {1} and cutoff of {2}".format(bestscore, besthistory, bestcutoff))
    confirmscore = confirmtests(data, besthistory, bestcutoff, testdays=60)
    print("Validation score of {0:.2f}%".format(confirmscore))

    print("If the above scores seem acceptable, you should use these options")
    print("soccerprediction.py -c \"{0}\" -l \"{1}\" -y {2} -b {3}".format(country, competition, besthistory, bestcutoff))
    print("\nGood Luck!")

else:
    # do the prediction - now takes number of historical games to use rather than using everything
    # added cutoff option which will printout game predictions with a probability higher than the cutoff
    data = poissonpredict(data, gamedate, history, cutoff)

    # save our predictions
    filename = datapath + country + "-" + competition.replace(" ", "-").replace("/", "-") + ".csv"
    data.to_csv(filename)
