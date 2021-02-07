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
import urllib.request
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
            print("Couldn't load date's page")
            return

        boxes = self.browser.find_elements_by_class_name("shadow-block")
        games = []
        for box in boxes:
            game_link = box.find_elements_by_class_name("text-cerulean")[1].get_attribute("href").split("#box")[0]
            game_name = game_link.split("/box")[0].split("/")[-1]
            games.append({"date": date, "game_name": game_name, "game_link":game_link})
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
        
        # Get list of games for specified date and their link
        games = self._get_games_link_for_date(date)
        
        # Loop over list of games link and meta data
        for game in games:

            # Load game page
            self.browser.get(game["game_link"])
            print(f"\nGetting data for game {game['game_name']} played on date {game['date']}")
            WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
            try:
                self.browser.find_element_by_id("onetrust-accept-btn-handler").click()
                time.sleep(2)
            except:
                pass

            # Create a folder for the game if it doesn't already exists
            game_path = f"{self.path_nba_games}/{date}/{game['game_name']}"
            self.make_sure_path_exists(f"{game_path}/")
            for data_type in ["Traditional", "Advanced", "Misc", "Scoring", "Usage", "Four Factors", "Player Tracking", "Hustle", "Defense", "Matchups"]:
                if data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        print(f"Couldnt scrape {data_type}")

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
                        dfs = _html_to_df()
                        matchups = dfs[0]
                        matchups.to_csv(f"{game_path}/matchups.csv", index=False)
                        print(f"--Exported {data_type} data")
                        matchups = pd.DataFrame()
                    except:
                        print("Couldn't click on ALL button")

                    # Move on the next data_type page
                    continue
                elif data_type != "Traditional":
                    try:
                        self.browser.find_element_by_xpath(f"//select[@name='splits']/option[text()='{data_type}']").click()
                    except:
                        print(f"Couldnt scrape {data_type}")

                        # Move on the next data_type page
                        continue    
                else:
                    #Get inactive players
                    WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                    inactive_players = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/aside')
                    inactive_players = [e.text for e in inactive_players.find_elements_by_tag_name('p')]
                    inactive_players = pd.DataFrame(inactive_players)
                    inactive_players[1:].to_csv(f"{game_path}/inactive_players.csv", index=False)
                
                WebDriverWait(self.browser, self.web_driver_wait).until(EC.presence_of_element_located((By.CLASS_NAME, 'antialiased')))
                dfs = _html_to_df()
                df_away = dfs[0]
                df_away.to_csv(f"{game_path}/away_{data_type.replace(' ', '_').lower()}.csv", index=False)
                print(f"--Exported away {data_type} data")
                df_home = dfs[1]
                df_home.to_csv(f"{game_path}/home_{data_type.replace(' ', '_').lower()}.csv", index=False)
                print(f"--Exported home {data_type} data")
                df_home = df_away = pd.DataFrame()

            # Collect summary data
            summary = game["game_link"].replace("box-score", "")
            self.browser.get(summary)
            time.sleep(3)
            dfs = _html_to_df()
            
            # Concatenate the two dataframe together
            df_summary = pd.concat([dfs[0], dfs[1]], axis=1).reindex(dfs[0].index)
            columns = list(df_summary.columns)
            columns[0] = "TEAM"
            df_summary.columns = columns
            df_summary.to_csv(f"{game_path}/summary.csv", index=False)
            df_summary = pd.DataFrame()
            print(f"--Exported summary data")

            # Get Recap
            recap = self.browser.find_element_by_id("story").text
            with open(f"{game_path}/recap.txt", "w") as text_file:
                text_file.write(recap)
            print("--Saved recap")

            # Get Game Info, Lead Changes and Times Tied
            lead_change = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[2]/div[1]/p[2]').text
            times_tied = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[2]/div[2]/p[2]').text
            location = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[2]/div[2]').text
            officials = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[3]/div[2]').text
            attendance = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/div/section/div/div[4]/div[2]').text
            df_game_info = pd.DataFrame([{"lead_change":lead_change, "times_tied":times_tied,"location":location, "officials":officials, "attendance": attendance}])
            df_game_info.to_csv(f"{game_path}/game_info.csv", index=False)
            df_game_info = pd.DataFrame()

            #TODO: get javascript variables containing IDs, broadcasters etc..

            # Download Gamebook % PDF
            gamebook = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[3]/a[1]').get_attribute("href")
            pdf = self.browser.find_element_by_xpath('//*[@id="__next"]/div[2]/div[4]/section/div/div/div[3]/a[2]').get_attribute("href")
            urllib.request.urlretrieve(gamebook, f"{game_path}/gamebook.pdf")
            print("--Downloaded Gamebook PDF")
            urllib.request.urlretrieve(pdf, f"{game_path}/game_pdf.pdf")
            print("--Downloaded Game PDF")

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
            play_by_play_df.to_csv(f"{game_path}/play_by_play.csv", index=False)
            print(f"--Exported play by play data")
            play_by_play_df = pd.DataFrame()
        return
    
        
    def schedule_to_csv(self):
        pass

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

if __name__ == '__main__':
    # execute only if run as the entry point into the program
    nba = NBAScraper()
    # nba.get_games_by_date("02/02/2020")
    nba.get_games_by_date()