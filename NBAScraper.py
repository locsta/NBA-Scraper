from selenium_scraper import Scraper

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
import subprocess
import os
import errno
import json
import time
import pandas as pd

from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common import exceptions
from datetime import date
from datetime import timedelta
from datetime import datetime
import requests
import re
import logging
import logging.handlers
import sys
import numpy as np
from os import listdir
from os.path import isfile, join
from pprint import pprint

import requests
from lxml.html import fromstring
from selenium.webdriver.common.proxy import Proxy, ProxyType

class NBAScraper(Scraper):
    def __init__(self):
        # Create a headless browser
        super().__init__(headless=False)
        self.browser = self.open_browser()
        self.web_driver_wait = 10
        self.path_data = os.path.normpath(os.path.expanduser("~/DATA"))
        self.path_nba = os.path.join(self.path_data, "NBA")
        self.path_nba_games = os.path.join(self.path_nba, "games")
        self.path_nba_schedule = os.path.join(self.path_nba, "schedule") 

    
    def _get_games_link_for_date(self, date=None):
        if not date:
            date = (datetime.now() - timedelta(days = 1)).strftime("%Y-%m-%d")
            
        self.browser.get(f"https://www.nba.com/games?date={date}")
        
        try:
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'shadow-block')))
        except:
            # TODO: use logging
            return

        boxes = self.browser.find_elements_by_class_name("shadow-block")
        games = []
        for box in boxes:
            game_link = box.find_elements_by_class_name("text-cerulean")[1].get_attribute("href").split("#box")[0]
            game_name = ("_".join((game_link.split("/box")[0].split("-"))[:-1])).split("/")[-1]
            game_id = game_link.split("/box")[0].split("-")[-1]
            games.append({"date": date, "game_name": game_name, "game_id":game_id, "game_link":game_link})
        return games
    
    def get_games_by_date(self, date=None):
        """This method collects the data in csv format for all the games played on the specified date
        data include: "Traditional", "Advanced", "Misc", "Scoring", "Usage", "Four Factors", "Player Tracking", "Hustle", "Defense", "Matchups", "Play by Play"

        Args:
            date ([type], optional): [The date must be specified in the YYYY/MM/DD format]. Defaults to yesterday.
        """

        def _html_to_df():
            # This private method format html tables in pandas DataFrame format
            html = self.browser.page_source
            soup = BeautifulSoup(html,'html.parser')
            tables = soup.select("table")
            dfs = []
            for table in tables:
                dfs.append(pd.read_html(str(table))[0])
            return dfs

        if not date:
            date = (datetime.now() - timedelta(days = 1)).strftime("%Y-%m-%d")
            
        games = self._get_games_link_for_date(date)
        
        for game in games:
            print(game["game_link"])
            self.browser.get(game["game_link"])
            print(f"Getting data for game {game['game_name']} played on the {game['date']}")
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
            try:
                self.browser.find_element_by_id("onetrust-accept-btn-handler").click()
                time.sleep(2)
            except:
                pass

            # Create a folder for the game if it doesn't already exists
            self.make_sure_path_exists(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/")
            for data_type in ["Traditional", "Advanced", "Misc", "Scoring", "Usage", "Four Factors", "Player Tracking", "Hustle", "Defense", "Matchups"]:
                if data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        print(f"Couldnt scrape {data_type}")
                        continue
                if data_type == "Matchups":
                    # Click on "Matchups" in the first dropdown menu
                    self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    time.sleep(3)

                    # Click on "All" in the second dropdown menu
                    self.browser.find_element_by_xpath(f"//select[@name='']/option[text()='All']").click()
                    time.sleep(3)
                    dfs = _html_to_df()
                    matchups = dfs[0]
                    matchups.to_csv(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/matchups.csv", index=False)
                    print(f"--Exported {data_type} data")
                    matchups = pd.DataFrame()
                    continue
                elif data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        print(f"Couldnt scrape {data_type}")
                        continue    
                else:
                    #Get inactive players
                    WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                    inactive_players = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/aside')
                    inactive_players = [e.text for e in inactive_players.find_elements_by_tag_name('p')]
                    inactive_players = pd.DataFrame(inactive_players)
                    inactive_players[1:].to_csv(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/inactive_players.csv", index=False)
                
                WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                dfs = _html_to_df()
                df_away = dfs[0]
                df_away.to_csv(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/away_{data_type.replace(' ', '_').lower()}.csv", index=False)
                print(f"--Exported away {data_type} data")
                df_home = dfs[1]
                df_home.to_csv(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/home_{data_type.replace(' ', '_').lower()}.csv", index=False)
                print(f"--Exported home {data_type} data")
                df_home = df_away = pd.DataFrame()

            # Collect play-by-play data
            play_by_play = game["game_link"].replace("box-score", "play-by-play")
            self.browser.get(play_by_play)
            time.sleep(3)
            try:
                self.browser.find_element_by_id("onetrust-accept-btn-handler").click()
            except:
                pass
            try:
                time.sleep(3)
                self.browser.find_element_by_xpath("//button[contains(text(),'ALL')]")
            except:
                print("Couldnt click on ALL button")
            
            # Selecting the div that contains the play-by-play articles
            box = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div[4]')

            # Selecting each article
            children = box.find_elements_by_xpath("./*")
            infos = []

            for child in children:
                # Get clock and action
                ps = child.find_elements_by_css_selector("p")
                clock = ""
                action = ""
                for p in ps:
                    if "clock" in p.get_attribute("class"):
                        clock = p.text
                    else:
                        action = p.text

                # If clock wasnt found it means that the article contain either start or end of quarter info
                if not clock:
                    clock = child.text # ex: Start of Q1
                    cell_away = ""
                    cell_home = ""

                # Check if action is perform for home or away team
                if "end" in child.get_attribute("class"):
                    cell_away = ""
                    cell_home = action
                elif "start" in child.get_attribute("class"):
                    cell_away = action
                    cell_home = ""

                # Append row to infos list
                infos.append({"away": cell_away, "clock": clock, "home": cell_home})
            play_by_play_df = pd.DataFrame(infos)
            play_by_play_df.to_csv(f"{self.path_nba_games}/{date}/{game['game_name']}_{game['game_id']}/play_by_play.csv", index=False)
            print(f"--Exported play by play data")
            play_by_play_df = pd.DataFrame()
        return

    def scrape_date(self, date):
        print(date)
        # date must be in the format dd_mm_yyyy
        day = date.split("_")[0]
        month = date.split("_")[1]
        year = date.split("_")[2]
        url = f"https://stats.nba.com/scores/{month}/{day}/{year}"
        self.browser.get(url)
        try:
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'bottom-bar')))
        except:
            try:
                WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'linescores-container')))
            except:
                print(f"Error scraping {url}")
                return
        self.make_sure_path_exists(self.path_nba_schedule)
        html_source = self.browser.page_source
        html_filename = os.path.join(self.path_nba_schedule, f"{date}.html")
        with open(html_filename, 'w') as f:
            f.write(html_source)
    
    def scrape_game_stats_by_id(self):
        df = pd.read_csv("/home/locsta/DATA/NBA/schedule.csv")
        # df = df[df["season"] == 2017] - ((df["season"] < 2009) | (df["season"] == 2009)) & 
        raw_game_ids = list(df.loc[(df["path"] != "error") & ((df["traditional"] != "x") | (df["advanced"] != "x") | (df["misc"] != "x") | (df["scoring"] != "x") | (df["usage"] != "x") | (df["four-factors"] != "x")), "game_id"])
        # raw_game_ids = [19800003,21900400, 19800005, 21700501]
        for raw_game_id in raw_game_ids:
            game_id = "00" + str(raw_game_id)
            print(game_id)
            # for detail in ["traditional", "advanced", "misc", "scoring", "usage", "four-factors"]:
            for detail in ["traditional", "advanced", "misc", "scoring", "usage", "four-factors"]:
                if [str(x) for x in df.loc[df["game_id"] == raw_game_id, detail]][0] == "x":
                    continue
                if detail == "traditional":
                    self.browser.get(f"https://stats.nba.com/game/{game_id}/")
                else:
                    self.browser.get(f"https://stats.nba.com/game/{game_id}/{detail}/")
                # time.sleep(5)
                print(f"     {detail}")
                try:
                    WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'player')))
                except:
                    try:
                        WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'player')))
                    except:
                        print(f"Error with {game_id}, details: {detail}")
                        self.browser.quit()
                        return
                gamecode = self.browser.find_element_by_class_name("game-summary-team").get_attribute("nba-with-gamecode")
                if not gamecode:
                    print("No gamecode found")
                    df.loc[df["game_id"] == raw_game_id, "path"] = "error"
                    df.to_csv(os.path.join(self.path_nba, "schedule.csv"), columns=["date", "game_id", "season", "home_team", "away_team", "home_team_id", "away_team_id", "arena", "home_broadcast", "away_broadcast", "natl_broadcast", "traditional", "advanced", "misc", "scoring", "usage", "four-factors", "path"], index=False)
                    break
                date = gamecode.split("/")[0]
                date = date[-2:] + "_" + date[4:6] + "_" + date[:4]
                game = gamecode.split("/")[1]
                if not gamecode:
                    print(f"No game for game id: {game_id}")
                    return
                path_date_folder = os.path.join(self.path_nba_games, date)
                path_game = os.path.join(path_date_folder, game)
                self.make_sure_path_exists(path_game)

                html_source = self.browser.page_source
                html_filename = os.path.join(path_game, f"{detail}.html")
                with open(html_filename, 'w') as f:
                    f.write(html_source)
                df.loc[df["game_id"] == raw_game_id, detail] = "x"
                df.loc[df["game_id"] == raw_game_id, "path"] = path_game
                df.to_csv(os.path.join(self.path_nba, "schedule.csv"), columns=["date", "game_id", "season", "home_team", "away_team", "home_team_id", "away_team_id", "arena", "home_broadcast", "away_broadcast", "natl_broadcast", "traditional", "advanced", "misc", "scoring", "usage", "four-factors", "path"], index=False)
        
    def schedule_to_csv(self):
        days = [f for f in listdir(self.path_nba_schedule) if isfile(join(self.path_nba_schedule, f))]
        for day in days:
            if not os.path.isfile(os.path.join(self.path_nba, "schedule.csv")):
                no_need_to_scrape = []
                df_schedule = pd.DataFrame()
            else:
                df_schedule = pd.read_csv(os.path.join(self.path_nba, "schedule.csv"))
                no_need_to_scrape = list(set(df_schedule.date))
            print(day)
            if day in no_need_to_scrape:
                continue
            with open(os.path.join(self.path_nba_schedule, day), 'r') as f:
                html = f.read()
            games_nb = len(re.findall('GAMECODE":"(.*?)"', html))
            if not games_nb:
                continue
            js = re.findall('GAME_DATE_EST":(.*?)WH_STATUS', html)
            date = day.replace("_","/").replace(".html", "")
            games = []
            for game in js:
                game_id = re.findall('GAME_ID":"(.*?)"', game)[0]
                print(game_id)
                gamecode = re.findall('GAMECODE":"(.*?)"', game)[0]
                home_team = re.findall('GAMECODE":"(.*?)"', game)[0].split("\/")[1][-3:]
                away_team = re.findall('GAMECODE":"(.*?)"', game)[0].split("\/")[1][:3]
                home_team_id = re.findall('HOME_TEAM_ID":(.*?),', game)[0]
                away_team_id = re.findall('VISITOR_TEAM_ID":(.*?),', game)[0]
                home_broadcast = re.findall('HOME_TV_BROADCASTER_ABBREVIATION":(.*?),', game)[0]
                away_broadcast = re.findall('AWAY_TV_BROADCASTER_ABBREVIATION":(.*?),', game)[0]
                natl_broadcast = re.findall('NATL_TV_BROADCASTER_ABBREVIATION":(.*?),', game)[0]
                season = re.findall('SEASON":"(.*?)"', game)[0]
                arena = re.findall('ARENA_NAME":"(.*?)"', game)[0]
                games.append({"date":date, "season": season, "game_id":game_id, "home_team":home_team, "away_team":away_team, "home_team_id":home_team_id, "away_team_id":away_team_id, "home_broadcast":home_broadcast, "away_broadcast":away_broadcast, "natl_broadcast":natl_broadcast, "arena":arena})
            df = pd.DataFrame(games)
            df_schedule = df_schedule.append(df)
            df_schedule.to_csv(os.path.join(self.path_nba, "schedule.csv"), columns=["date", "game_id", "season", "home_team", "away_team", "home_team_id", "away_team_id", "arena", "home_broadcast", "away_broadcast", "natl_broadcast"], index=False)
        time.sleep(2)
        df = pd.read_csv(os.path.join(self.path_nba, "schedule.csv"))
        df["game_type"] = df["game_id"].map(lambda x : "playoff" if str(x)[0] == "4" else ("preseason" if str(x)[0] == "1" else ("regular" if str(x)[0] == "2" else "allstar")))
        df["datetime"] = pd.to_datetime(df["date"], format = '%d/%m/%Y')
        df = df.sort_values(by=['datetime'])
        df.drop(["datetime"], axis=1,inplace=True)
        df = df.drop_duplicates(subset=['game_id'])
        df_summary = df.groupby(["game_type","season"]).agg("count")
        df_summary = df_summary.sort_values(by=['season'])
        df["traditional"] = ""
        df["advanced"] = ""
        df["misc"] = ""
        df["scoring"] = ""
        df["usage"] = ""
        df["four-factors"] = ""
        df["path"] = ""
        df.to_csv(os.path.join(self.path_nba, "schedule.csv"), columns=["date", "game_id", "season", "game_type" ,"home_team", "away_team", "home_team_id", "away_team_id", "arena", "home_broadcast", "away_broadcast", "natl_broadcast", "traditional", "advanced", "misc", "scoring", "usage", "four-factors", "path"], index=False)
        df_summary.to_csv(os.path.join(self.path_nba, "summary.csv"))

    def get_game_stats_by_id(self, game_id):
        # self.browser.get(f"https://stats.nba.com/game/{game_id}/")
        location = f"file:///home/locsta/Documents/NBA-Project/DATA/NBA_website/20060419/DENSEA/20060419_DENSEA.html"
        self.browser.get(location)
        # time.sleep(5)
        try:
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'score')))
        except:
            try:
                WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'score')))
            except:
                return
        # GAME INFOS
        gamecode = self.browser.find_element_by_class_name("game-summary-team").get_attribute("nba-with-gamecode")
        if not gamecode:
            print(f"No game for game id: {game_id}")
            return
        path_game = os.path.join(self.path_nba_games, gamecode)
        self.make_sure_path_exists(path_game)

        away_team = self.browser.find_elements_by_class_name("team-name")[0].text
        home_team = self.browser.find_elements_by_class_name("team-name")[1].text
        lead_changes = self.browser.find_element_by_class_name("game-summary-other__lead-changes").find_element_by_css_selector("td").text
        times_tied = self.browser.find_element_by_class_name("game-summary-other__tied").find_element_by_css_selector("td").text
        a_lineups_url = self.browser.find_elements_by_class_name("game-summary-team__lineup")[0].find_element_by_css_selector("a").get_attribute("href")
        h_lineups_url = self.browser.find_elements_by_class_name("game-summary-team__lineup")[1].find_element_by_css_selector("a").get_attribute("href")
        additional_infos = self.browser.find_element_by_class_name("game-summary-additional__inner").text
        records = self.browser.find_elements_by_class_name("game-summary-team__record")
        a_team_record = records[0].text
        h_team_record = records[1].text

        stat_box = self.browser.find_element_by_class_name("game-summary-other").find_element_by_css_selector("tbody")
        stats_index = stat_box.find_elements_by_css_selector("tr")
        
        ### SCORES ###
        quarters = ["qtr1", "qtr2", "qtr3", "qtr4", "ot1", "ot2", "ot3", "ot4", "ot5", "ot6", "ot7", "ot8", "ot9", "ot10", "final"]
        team_stats = ["PITP", "2ND_PTS", "FBPS", "BIG_LD", "TM_REB", "TM_TOV", "TOT_TOV", "OPP_TOV_PTS"]
        scores = {}
        for index in [0, 1]:
            scores[index] = {}
            ### Quarters ###
            for quarter in quarters:
                scores[index][quarter] = self.browser.find_elements_by_class_name(quarter)[index+1].text
            ### Stats ###
            stats = stats_index[index].find_elements_by_css_selector("td")
            for stat_index, team_stat in enumerate(team_stats):
                scores[index][team_stat] = stats[stat_index].text
        
        scores[0]["AWAY/HOME"] = "AWAY"
        scores[1]["AWAY/HOME"] = "HOME"
        scores[0]["TEAM"] = away_team
        scores[1]["TEAM"] = home_team
        scores[0]["LINEUPS_URL"] = a_lineups_url
        scores[1]["LINEUPS_URL"] = h_lineups_url
        scores[0]["RECORD"] = a_team_record
        scores[1]["RECORD"] = h_team_record
        df = pd.DataFrame(scores)
        df = df.T
        df.to_csv(os.path.join(path_game, "game_stats.csv"), columns=["AWAY/HOME", "TEAM", "qtr1", "qtr2", "qtr3", "qtr4", "ot1", "ot2", "ot3", "ot4", "ot5", "ot6", "ot7", "ot8", "ot9", "ot10", "final", "PITP", "2ND_PTS", "FBPS", "BIG_LD", "TM_REB", "TM_TOV", "TOT_TOV", "OPP_TOV_PTS", "RECORD", "LINEUPS_URL"], index=None)
        gametime = additional_infos.split("\n")[0].replace("GAMETIME: ", "")
        attendance = additional_infos.split("\n")[1].replace("ATTENDANCE: ", "").replace(",", "")
        officials = additional_infos.split("\n")[2].replace("OFFICIALS: ", "").split(", ")
        if len(officials) == 2:
            officials.append("")
        game_infos = {0: {"GAME_ID": game_id, "LEAD_CHANGES": lead_changes, "TIMES_TIED": times_tied,"GAMETIME": gametime, "ATTENDANCE": attendance, "REF1": officials[0], "REF2": officials[1], "REF3": officials[2]}}
        df = pd.DataFrame(game_infos)
        df = df.T
        df["GAMETIME"] = df["GAMETIME"].map(self.timedelta_gametime)
        df["GAMETIME"] = pd.to_timedelta(df["GAMETIME"], unit="s")
        df.to_csv(os.path.join(path_game, "game_details.csv"), columns=["GAME_ID", "GAMETIME", "LEAD_CHANGES", "TIMES_TIED", "REF1", "REF2", "REF3"], index=None)

        ### PLAYER STATS ###
        stat_names = ["PLAYER", "MIN", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "PF", "PTS", "+/-"]
        tables = self.browser.find_elements_by_class_name("nba-stat-table")
        players_h = []
        players_a = []
        for t_n, table in enumerate(tables):
            trs = table.find_element_by_css_selector("tbody").find_elements_by_css_selector("tr")
            for tr in trs:
                tds = tr.find_elements_by_css_selector("td")
                player = {}
                for i, td in enumerate(tds):
                    if i == 0:
                        player["ID"] = td.find_element_by_css_selector("a").get_attribute("href").replace("https://stats.nba.com/player/", "").replace("/", "")
                        try:
                            starting = td.find_element_by_css_selector("a").find_element_by_css_selector("sup").text
                        except:
                            starting = ""
                        if starting:
                            player["PLAYER"] = td.text.replace(" " + starting, "")
                        else:
                            player["PLAYER"] = td.text
                        player["STARTER"] = starting
                    else:
                        player[stat_names[i]] = td.text
                if t_n == 0:
                    players_a.append(player)
                else:
                    players_h.append(player)

        # INACTIVE PLAYERS #
        inactive_players = self.browser.find_element_by_class_name("game-summary__inactive").text.split("\n")
        h_inactives = inactive_players[2].replace(":", ":,").split(", ")[1:]
        for player in h_inactives:
            players_h.append({"ID":"", "PLAYER": player, "MIN": "", "FGM": "INACTIVE"})
        a_inactives = inactive_players[1].replace(":", ":,").split(", ")[1:]
        for player in a_inactives:
            players_a.append({"ID":"", "PLAYER": player, "MIN": "", "FGM": "INACTIVE"})
        df_h = pd.DataFrame(players_h)
        df_a = pd.DataFrame(players_a)
        int_cols = ["+/-", "3P%", "3PA", "3PM","AST", "BLK", "DREB", "FG%", "FGA", "FGM", "FT%", "FTA", "FTM", "OREB", "PF", "PTS", "REB", "STL", "TOV"]
        for df in [df_h, df_a]:
            # df["PLAYER"] = df["PLAYER"].map(self.rename)
            df["STATUS"] = df["FGM"].map(self.status)
            df["ID"] = df["ID"].map(lambda x: x.replace("https://stats.nba.com/player/", "").replace("/",""))
            df["MIN"] = df["MIN"].map(self.timedelta)
            df["MIN"] = pd.to_timedelta(df["MIN"], unit="s")
            # for col in int_cols:
            #     df[col] = pd.to_numeric(df[col], errors='coerce')
        df_h.to_csv(os.path.join(path_game, "home_team.csv"), columns=["PLAYER", "ID", "STATUS", "STARTER", "MIN", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "PF", "PTS", "+/-"], index=None)
        df_a.to_csv(os.path.join(path_game, "away_team.csv"), columns=["PLAYER", "ID", "STATUS", "STARTER", "MIN", "FGM", "FGA", "FG%", "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "OREB", "DREB", "REB", "AST", "TOV", "STL", "BLK", "PF", "PTS", "+/-"], index=None)
    
    def get_games(self):
        n = 20501230 #21600617
        while True:
            game_id = "00" + str(n)
            print(f"Getting data for game id {game_id}")
            self.get_game_stats_by_id(game_id)
            n = n - 1
            # if n == 21600804:
            #     quit()

    def scrape_dates_from_date_to_date(self, start_date, end_date):
        # dates must be in the format dd_mm_yyyy
        current_date = end_date
        while current_date != start_date:
            self.scrape_date(current_date)
            current_date_datime = datetime.strptime(current_date, "%d_%m_%Y")
            current_date = (current_date_datime - timedelta(days=1)).strftime("%d_%m_%Y")

    def get_player_stats(self, player_id):
        player_stats_url_ex = "https://stats.nba.com/player/1626174/"
        pass

    def export_players(self):
        pass
    
    def status(self, x):
        if x.startswith("DN"):
            return x
        elif x.startswith("INACTIVE"):
            return "INACTIVE"
        else:
            return "ACTIVE"

    def timedelta(self, x):
        if x == "":
            return 0
        times = x.split(":")
        mins = int(times[0])
        seconds = int(times[1])
        return 60*mins + seconds

    def timedelta_gametime(self, x):
        if x == "":
            return 0
        times = x.split(":")
        hours = int(times[0])
        minutes = int(times[1])
        return (60*hours + minutes)*60

    def get_proxies(self):
        url = 'https://free-proxy-list.net/'
        response = requests.get(url)
        parser = fromstring(response.text)
        proxies = set()
        for i in parser.xpath('//tbody/tr')[:20]:
            if i.xpath('.//td[7][contains(text(),"yes")]'):
                #Grabbing IP and corresponding PORT
                proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
                proxies.add(proxy)
        return proxies

# while True:
#     n = NBAScraper()
#     startTime = datetime.now()
#     n.scrape_game_stats_by_id()
#     print(datetime.now() - startTime)
#     time.sleep(10)



# n.schedule_to_csv()
# n.get_games()
# n.scrape_dates_from_date_to_date("01_07_1980", "03_08_1986")
# quit()
# for game_id in ["0021900895", "0011900001"]:
#     n.scrape_game_stats_by_id(game_id)
# n.get_game_stats_by_id("0021900960")

# date = date.today().strftime("%d_%m_%Y")
# yesterday = (date.today()- timedelta(days=1)).strftime("%d_%m_%Y")




# proxies = get_proxies()
# print(proxies)

if __name__ == '__main__':
    # execute only if run as the entry point into the program
    nba = NBAScraper()
    # nba.get_games_by_date("02/02/2020")
    nba.get_games_by_date()