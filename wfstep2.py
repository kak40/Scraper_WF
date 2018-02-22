#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb 17 19:17:03 2018

@author: karine
"""

from selenium import webdriver
from time import sleep, time
from bs4 import BeautifulSoup
import os
import json # see http://stackabuse.com/reading-and-writing-json-to-a-file-in-python/ for example
import re
import pandas as pd


##Step 1: get countries url
def get_countries(url):
    """
    get all countries url from an url
    """
    options = webdriver.firefox.options.Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(firefox_options=options)
    driver.get(url)
    sleep(5)  # Anti anti-bot measure
    html = driver.page_source
    driver.close()    # be polite, close

    soup = BeautifulSoup(html, "html.parser")
    f = open("country.txt", "w",encoding='utf-8')
    f.write(soup.prettify())
    f.close()

    codes = soup.find_all("option")
    countries = []
    for code in codes:
        # model : http://www.4coffshore.com/windfarms/contracts-on-rentel-Be05.html
        countries.append({"url":"http://www.4coffshore.com/windfarms/contracts-on-rentel-" + code.attrs['value'] + ".html",
                          "country_name":code.text})
    
    return countries


# step 2 : get all windfarms by countries
# countryurl = 'http://www.4coffshore.com/windfarms/contracts-on-rentel-TN01.html'

def farms_from_html(html):
    """
    from an html code, gives the list of farms's links and name as a dictionnary
    applied on 1 page ! (some countries have several farms pages)
    """
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", {"class": "linkWF"})
    # comprehensive list
    return [{"url": "http://www.4coffshore.com/windfarms/contracts-on-"+ link.attrs["href"].split('/')[-1],
             "farm_name": link.span.text} for link in links]

def get_country_farms(url):
    """
    from a country url, gives the list of all farm's url and names as a dictionary
    handle all farms pages
    """
    options = webdriver.firefox.options.Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(firefox_options=options)
    print(url,type(url))
    driver.get(url)
    sleep(5)
    html = driver.page_source
    
    if driver.current_url.endswith('404.aspx'):
        driver.close() # dirty !!!
        return []
    
    #on scan les farms de la page 1
    farms = farms_from_html(html)
    listpages = re.findall(r'Page\$[0-9]', html)
    # /2 pour les deux pager (haut/bas)
    # +1 car le premier liens, déjà cliqué, n'a pas de liens clickable
    n_volets = len(listpages)//2 +1
    
    for i in range(2, n_volets+1):
        # on trouve le bouton str(i), on le click et on scan les farms
        button = driver.find_element_by_link_text(str(i))
        driver.execute_script("arguments[0].scrollIntoView();", button)
        button.click()
        sleep(3) # necessary for page to act upon click
        
        # on relit la source à jour
        html = driver.page_source
        farms += farms_from_html(html)
    
    driver.close()
    
    return farms



# step 3 get supply chain
def get_info_from_line(line, class_identifier):
    tmp= line.find('div', attrs={'class': class_identifier})
    if tmp:
        tmp = tmp.a
        if tmp:
            return tmp.text
        else:
            return 'NaN'
    else:
        return 'NaN'


def get_supply_chain(farm):
    print("in !")
    options = webdriver.firefox.options.Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(firefox_options=options)
    print(farm["url"],type(farm["url"]))
    driver.get(farm["url"])
    sleep(8)
    html = driver.page_source
    driver.close()
    
    soup = BeautifulSoup(html, "html.parser")
    country_name = soup.find("img", {"id":"ctl00_Body_Page_SubMenu_imgFlag"}).attrs["title"]
    
    datas = []
    for block in soup.find_all('h3')[:-1]:  #last h3: site's phone number, no need
        # block is ONE accordeon part
        fulltitle = block.text
        res = re.search(r"([\w\s/]+) \((\d*)", fulltitle)
        nbr = int(res.group(2))
        title = res.group(1)
        if nbr != 0:
            divcontent = block.nextSibling.nextSibling
            for line in divcontent.find_all("tr")[1:]:
                role = line.find('span', attrs={'class': "gvshRole"}).text
                org_descrp = get_info_from_line(line, "gvshOrg")
                farm_descrp = get_info_from_line(line, "gvshDesc")
                datas.append({'country': country_name, "farm": farm["farm_name"], 'role': role, 'categorie': title, 'organisation': org_descrp, 'content': farm_descrp})
        else:
            print('empty categorie. skip')
            
    return datas



# create data dir if it doesn't exist
directory = '/home/kakinew/BigData/Python/countries-datas'
if not os.path.exists(directory):
    os.makedirs(directory)
    
# removing errorfile if it exists
errorfile = os.path.join(directory,'errorlog.txt')
if os.path.exists(errorfile):
    os.remove(errorfile)
    
baseurl = "http://www.4coffshore.com/windfarms/contracts-on-arkona-de46.html"
countries = get_countries(baseurl)
start = time()
print(len(countries), "countries found !")
for i, country in enumerate(countries):
    # define a filename (with path) for the country
    file = os.path.join(directory, country["country_name"]+'.json')
    
    if os.path.isfile(file):
        print(file, "already exist, skipping this country as we have already done it \o/")
    else:
        try:
            sleep(1)
            print('getting farms from country', country["country_name"], i+1,'/',len(countries))
            country_farm = get_country_farms(country["url"])
            print(len(country_farm), "farms found")
        except:
            print('an error occured in country', country["country_name"])
            errorlog = open(errorfile, 'a')
            errorlog.write('error getting farms on country url: '+country["url"]+' \n')
            errorlog.close()
            continue # goes to the next country
            
        # recording all data from the country
        datas = []
        try:
            for j, farm in enumerate(country_farm):
                print('getting data from farm', farm["farm_name"], j+1,'/',len(country_farm))
                data_farm = get_supply_chain(farm)
                print(len(data_farm), 'data found')
                datas += data_farm
                print("elapsed time :", time()-start)
            print("saving", len(datas), 'datas found for country', country["country_name"])
            with open(file, 'w') as jsonfile:  
                json.dump(datas, jsonfile, indent=2) # indent will pretty-print
        except:
            # will catch all error on the above block
            print('an error occured on farm', farm["farm_name"])
            errorlog = open(errorfile, 'a')
            errorlog.write('error on last farm url: '+farm["url"]+' \n')
            errorlog.close()
            continue # goes to the next country
            
# concatenate all json back into a datas list
datas = []
for file in os.listdir(os.path.join('.',directory)):
    fullpath = os.path.join(directory, file)
    print(fullpath)
    if fullpath.endswith('.json'): # exclude errorlog.txt
        with open(fullpath) as jsonfile:  
            datas += json.load(jsonfile)


#convert data to csv
da = pd.DataFrame(datas)
da.to_csv("/home/kakinew/BigData/Python/data.csv",encoding="utf-8")
