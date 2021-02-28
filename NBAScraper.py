# Selenium & other web oriented libraries
from selenium_scraper import Scraper
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common import exceptions
from selenium.webdriver.common.proxy import Proxy, ProxyType
from lxml.html import fromstring
from bs4 import BeautifulSoup
import requests

# OS & Data libraries
from os import listdir
from os.path import isfile, join
import os
import sys
import json
import pandas as pd

# Time
import time
from datetime import date
from datetime import timedelta
from datetime import datetime

class NBAScraper(Scraper):
    def __init__(self):
        # Create a headless browser
        super().__init__(headless=False, log_filename=os.path.basename(__file__).replace(".py", ".log"))
        self.browser = self.open_browser()
        self.web_driver_wait = 10
        self.path_data = os.path.normpath(os.path.expanduser("~/DATA"))
        self.path_nba = os.path.join(self.path_data, "NBA")
        self.path_nba_games = os.path.join(self.path_nba, "games")
        self.path_nba_schedule = os.path.join(self.path_nba, "schedule.csv")
    
    def _get_games_link_for_date(self, date=None):
        """This private method aims to get links of games of the specified date

        Args:
            date ([type], optional): [The date needs to be in YYYY/MM/DD format]. Defaults to Yesterday.

        Returns:
            [type]: [List of game dictionaries containing for each game: the date of the game, the game name and the game link]
        """
        if not date:
            date = (datetime.now() - timedelta(days = 1)).strftime("%Y-%m-%d")
            
        self.browser.get(f"https://www.nba.com/games?date={date}")
        
        try:
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'shadow-block')))
        except:
            self.logging.error("Couldn't load date's page")
            return

        boxes = self.browser.find_elements_by_class_name("shadow-block")
        games = []
        for box in boxes:
            game_link = box.find_elements_by_class_name("text-cerulean")[1].get_attribute("href").split("#box")[0]
            game_name = game_link.split("/box")[0].split("/")[-1]
            games.append({"date": date, "game_name": game_name, "game_link":game_link})
        return games
    
    def _get_game_summary(self, game, game_path):
        # Collect summary data
        summary = game["game_link"].replace("box-score", "")
        self.browser.get(summary)
        time.sleep(3)
        dfs = self.html_tables_to_df()
        
        # Concatenate the two dataframe together
        df_summary = pd.concat([dfs[0], dfs[1]], axis=1).reindex(dfs[0].index)
        columns = list(df_summary.columns)
        columns[0] = "TEAM"
        df_summary.columns = columns
        df_summary.to_csv(f"{game_path}/summary.csv", index=False)
        df_summary = pd.DataFrame()
        self.logging.info("Exported summary data")

        # Get Recap
        recap = self.browser.find_element_by_id("story").text
        with open(f"{game_path}/recap.txt", "w") as text_file:
            text_file.write(recap)
        self.logging.info("Saved recap")

        # Get Game Info, Lead Changes and Times Tied
        lead_change = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[2]/div[1]/p[2]').text
        times_tied = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[2]/div[2]/p[2]').text
        location = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[2]/div[2]').text
        officials = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[3]/div[2]').text
        attendance = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[4]/div[2]').text
        df_game_info = pd.DataFrame([{"lead_change":lead_change, "times_tied":times_tied,"location":location, "officials":officials, "attendance": attendance}])
        df_game_info.to_csv(f"{game_path}/game_info.csv", index=False)
        df_game_info = pd.DataFrame()

        # Saving script content containing meta data
        self.script_data_from_id_to_json("__NEXT_DATA__", f"{game_path}/meta_data.json")
        self.logging.info("Saved metadata")

        # Download Gamebook % PDF
        gamebook = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[3]/a[1]').get_attribute("href")
        pdf = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[3]/a[2]').get_attribute("href")
        self.download(gamebook, f"{game_path}/gamebook.pdf")
        self.download(pdf, f"{game_path}/game_pdf.pdf")
        return

    def _get_game_play_by_play(self, game, game_path):
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
            self.logging.warning("Couldnt click on ALL button")
        
        # Selecting the div that contains the play-by-play articles
        try:
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
            play_by_play_df.to_csv(f"{game_path}/play_by_play.csv", index=False)
            self.logging.info(f"Exported play by play data")
            play_by_play_df = pd.DataFrame()
        except:
            self.logging.warning("Couldn't scrape play by play data")
    
    def get_game(self, game, game_date, data_types=[]):
        if not game:
            return
        else:
            # Load game page
            self.browser.get(game["game_link"])
            self.logging.info(f"\nGetting data for game {game['game_name']} played on date {game['date']}")
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
            try:
                self.browser.find_element_by_id("onetrust-accept-btn-handler").click()
                time.sleep(2)
            except:
                pass

            # Create a folder for the game if it doesn't already exists
            game_path = f"{self.path_nba_games}/{game_date}/{game['game_name']}"
            self.make_sure_path_exists(f"{game_path}/")
            if data_types == []:
                data_types = ["Traditional", "Advanced", "Misc", "Scoring", "Usage", "Four Factors", "Player Tracking", "Hustle", "Defense", "Matchups", "Summary", "Play by play"]
            scrape_summary = scrape_play_by_play = False
            if "Summary" in data_types:
                scrape_summary = True
                data_types.remove("Summary")
                
            if "Play by play" in data_types:
                data_types.remove("Play by play")
                scrape_play_by_play = True
                

            for data_type in data_types:
                if data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        self.logging.warning(f"Couldnt scrape {data_type}")

                        # Move on the next data_type page
                        continue

                if data_type == "Matchups":
                    # Click on "Matchups" in the first dropdown menu
                    self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    time.sleep(3)

                    # Click on "All" in the second dropdown menu
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='']/option[text()='All']").click()
                        time.sleep(3)
                        dfs = self.html_tables_to_df()
                        matchups = dfs[0]
                        matchups.to_csv(f"{game_path}/matchups.csv", index=False)
                        self.logging.info(f"Exported {data_type} data")
                        matchups = pd.DataFrame()
                    except:
                        self.logging.warning("Couldn't click on ALL button")

                    # Move on the next data_type page
                    continue
                elif data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        self.logging.warning(f"Couldnt scrape {data_type}")

                        # Move on the next data_type page
                        continue    
                else:
                    # Get inactive players
                    WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                    inactive_players = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/aside')
                    inactive_players = [e.text for e in inactive_players.find_elements_by_tag_name('p')]
                    inactive_players = pd.DataFrame(inactive_players)
                    inactive_players[1:].to_csv(f"{game_path}/inactive_players.csv", index=False)
                
                WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                dfs = self.html_tables_to_df()
                df_away = dfs[0]
                df_away.to_csv(f"{game_path}/away_{data_type.replace(' ', '_').lower()}.csv", index=False)
                self.logging.info(f"Exported away {data_type} data")
                df_home = dfs[1]
                df_home.to_csv(f"{game_path}/home_{data_type.replace(' ', '_').lower()}.csv", index=False)
                self.logging.info(f"Exported home {data_type} data")
                df_home = df_away = pd.DataFrame()

            if scrape_summary:
                self._get_game_summary(game, game_path)
            if scrape_play_by_play:
                self._get_game_play_by_play(game, game_path)
        return
    
    
    def get_games_by_date(self, date=None):
        """This method collects the data in csv format for all the games played on the specified date
        data include: "Traditional", "Advanced", "Misc", "Scoring", "Usage", "Four Factors", "Player Tracking", "Hustle", "Defense", "Matchups", "Play by Play"

        Args:
            date ([type], optional): [The date must be specified in the YYYY/MM/DD format]. Defaults to yesterday.
        """

        if not date:
            date = (datetime.now() - timedelta(days = 1)).strftime("%Y-%m-%d")
        
        # Get list of games for specified date and their link
        games = self._get_games_link_for_date(date)
        
        # Loop over list of games link and meta data
        for game in games:
            self.get_game(game, game_date=str(date))
    
    def schedule_to_csv(self):
        schedule_df = pd.DataFrame([{"test":"lol"}, {"test": "kikoo"}])
        schedule_df.to_csv(self.path_nba_schedule)
        self.logging.info("Saved schedule to CSV file")

if __name__ == '__main__':
    # execute only if run as the entry point into the program
    nba = NBAScraper()
    # nba.schedule_to_csv()
    # nba.get_games_by_date("02/02/2020")
    nba.get_games_by_date()