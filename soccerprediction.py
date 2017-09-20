import pandas as pd
from bs4 import BeautifulSoup as bs
from selenium import webdriver
import datetime
from os import path, makedirs
import numpy as np
import argparse


def scrapeseason(country, comp, season):
    # output what the function is attempting to do.
    print("Scraping:", country, comp, str(season)+"-"+str(season+1))
    baseurl = "http://www.soccerpunter.com/soccer-statistics/"
    scrapeaddress = (baseurl + country + "/" + comp.replace(" ", "-").replace("/", "-") + "-"
                     + str(season) + "-" + str(season + 1) + "/results")
    print("URL:", scrapeaddress)
    print("")

    # scrape the page and create beautifulsoup object
    sess = webdriver.PhantomJS()
    sess.get(scrapeaddress)
    page = bs(sess.page_source, "lxml")

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
        for s in range(startseason, currentseason+1):
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


def poissonpredict(df, gamedate, historylength):
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
        homeTeamAttackStrength = homeTeamHomeAvgFor/homeAvg
        homeTeamDefenceStrength = homeTeamHomeAvgAgainst/awayAvg

        # repeat for away team
        awayTeamAwayAvgFor = historical.loc[df["awayTeam"] == at, "awayScore"].mean()
        awayTeamAwayAvgAgainst = historical.loc[df["awayTeam"] == at, "homeScore"].mean()
        awayTeamAttackStrength = awayTeamAwayAvgFor/awayAvg
        awayTeamDefenceStrength = awayTeamAwayAvgAgainst/homeAvg

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
        df.ix[i, "homeWinProbability"] = homeTeamWins
        df.ix[i, "draws"] = draws
        df.ix[i, "awayTeamWins"] = awayTeamWins
        df.ix[i, "totalGoals"] = totalGoals
        df.ix[i, "threeOrMoreGoals"] = threeOrMoreGoals
        df.ix[i, "bothTeamsToScore"] = bothTeamsToScore

    return df


todaysdate = datetime.date.today().strftime("%Y-%m-%d")

# initialise parser object to read from command line
parser = argparse.ArgumentParser()

# add our required arguments
parser.add_argument("-u", "--update", action="store_true", help="Update with latest scores")
parser.add_argument("-c", "--country", default="England", help="Country to read data for")
parser.add_argument("-l", "--league", default="Premier League", help="Competition/League to read data for")
parser.add_argument("-d", "--date", default=todaysdate, help="Date of games to predict YYYY-MM-DD, eg 2017-09-20")
parser.add_argument("-p", "--path", default="data/", help="Path to store data files, relative to location of this file")
parser.add_argument("-y", "--history" , default=100, type=int, help="Number of historical games to consider")

# parse the arguments from the command line input and store them in the args variable
args = parser.parse_args()

# read from the args variable and store in more sensible vars
country = args.country
competition = args.league
gamedate = args.date
datapath = args.path
history = args.history

# if update requested then update, otherwise just use the existing data
if args.update:
    data = updatecompetitiondata(country, competition, 2014, datapath)
else:
    data = getcompetitiondata(country, competition, 2014, datapath)

# do the prediction - now takes number of historical games to use rather than using everything
data = poissonpredict(data, gamedate, history)

# save our predictions
filename = datapath + country + "-" + competition.replace(" ", "-").replace("/", "-") + ".csv"
data.to_csv(filename)


