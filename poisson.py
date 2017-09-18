import pandas as pd
from bs4 import BeautifulSoup as bs
from selenium import webdriver
import datetime
from os import path
import numpy as np

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


def poissonpredict(df, gamedate):
    # set the amount of simulations to run on each game
    simulatedgames = 100000

    # only use games before the date we want to predict
    historical = df.loc[df["date"] < str(gamedate)]

    # make sure we only use games that have valid scores
    historical = historical.loc[df["homeScore"] > -1]

    # games to predict
    topredict = df.loc[df["date"] == str(gamedate)]

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

        # store our prediction into the dataframe
        df.ix[i, "homeWinProbability"] = homeTeamWins
        df.ix[i, "draws"] = draws
        df.ix[i, "awayTeamWins"] = awayTeamWins

    return df


if not path.isfile("data.csv"):
    # set which country and competition we want to use
    # others to try, "Scotland" & "Premiership" or "Europe" & "UEFA Champions League"
    country = "England"
    competition = "Premier League"
    lastseason = 2016
    thisseason = 2017

    lastseasondata = scrapeseason(country, competition, lastseason)
    thisseasondata = scrapeseason(country, competition, thisseason)

    # combine our data to one frame
    data = pd.concat([lastseasondata, thisseasondata])
    data.reset_index(inplace=True, drop=True)

    # save to file so we don't need to scrape multiple times
    data.to_csv("data.csv")
else:
    # load our csv
    data = pd.read_csv("data.csv", index_col=0, parse_dates=True)

gamedate = datetime.date.today()
data = poissonpredict(data, gamedate)

data.to_csv("data.csv")


