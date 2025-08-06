
import os
import time
import json
import logging
import datetime
import requests
import multiprocessing
from bs4 import BeautifulSoup
from urllib.parse import unquote
from random import randint, choice, uniform
from modules.dbSync import updateMYSQL
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

# ------------------------------ LOGGER ------------------------------
import logging
def loggerInit(logFileName):
    try: os.makedirs("logs")
    except: pass
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
    file_handler = logging.FileHandler(f'logs/{logFileName}')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger
logger = loggerInit(logFileName="google.scrapper.module.log")
# ------------------------------ LOGGER ------------------------------

def init_selenium_driver(useVPN=False, IpCheck=False):
    """
    Initialize the Selenium driver with headless options
    """
    logger.debug(f"useVPN: {useVPN}")
    logger.debug(f"trigger selenium")
    from seleniumwire import webdriver
    
    driverPath = "/root/public/GcodeFinderBrandMpn(AF)/driver/chromedriver"
    with open("/root/public/GcodeFinderBrandMpn(AF)/vpn.config.json") as json_data_file:
        configs = json.load(json_data_file)
    for atmpt in range(5):
        try:
            VPN_User = configs['VPN_User']
            VPN_Pass = configs['VPN_Pass']
            VPN_IP_PORT = configs['VPN_IP_PORT'][randint(0, len(configs['VPN_IP_PORT']) - 1)]
            seleniumwire_options = {
                'backend': 'mitmproxy',
                'request_storage_base_dir': '/tmp/seleniumwire',  # optional, for large requests
                'connection_timeout': 30,  # default is 10
                'read_timeout': 60,  # Adjust the read timeout to 60 seconds
                'proxy': {
                    'http': f'http://{VPN_User}:{VPN_Pass}@{VPN_IP_PORT}',
                    'https': f'https://{VPN_User}:{VPN_Pass}@{VPN_IP_PORT}',
                    'no_proxy': 'localhost,127.0.0.1'
                }
            }

            # chrome options
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-setuid-sandbox") 
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument('--disable-blink-features')
            chrome_options.add_argument("--headless")            
            chrome_options.add_argument("start-maximized")
            chrome_options.add_argument("--disable-dev-shm-using") 
            chrome_options.add_argument("--disable-gpu") 
            chrome_options.add_argument("disable-infobars")
            # chrome_options.binary_location = '/opt/google/chrome/chrome'

            service = ChromeService(driverPath)
            if useVPN:
                driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options,
                    seleniumwire_options=seleniumwire_options
                )
            else:
                driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )

            # Check IP address
            try:
                if IpCheck:
                    time.sleep(randint(10000, 100000) / 10000)
                    driver.get("https://api.ipify.org?format=json")
                    time.sleep(randint(50,150)/1000)
                    for request in driver.requests:
                        if request.response:
                            if 'ipify' in request.url:
                                ip_info = json.loads(request.response.body.decode('utf-8'))
                                ip_address = ip_info.get('ip', 'IP not found')
                                logger.debug(f"Current IP: {ip_address}")
                                break
                return driver
            except:
                driver.get_screenshot_as_file(f"logs/ss/ip-check-exception.png")
                driver.quit()
                raise Exception("BadSession")
        except Exception as e:
            exception_messages = [
                "Chrome failed to start",
                "failed to start a thread",
                "chromedriver unexpectedly exited",
                "Failed to create Chrome process",
                "Resource temporarily unavailable",
                "can't start new thread"
            ]
            if any(filter(lambda msg: str(msg) in str(e), exception_messages)):
                logger.debug("""
                ---------- Chrome is crashing, rebooting ----------
                """)
                os.system(f"/sbin/shutdown -r now")
            
            logger.debug(f"Attempting ({atmpt + 1}/5) >> {e}")
            if atmpt == 4: raise e

def random_boolean():
    return choice([True, False])

# Scarpping data via gcode
def fetchMatchedData(found_gcode, productID, productURL):
    logger.debug(f"Scrapping ({found_gcode})")
    
    driver = init_selenium_driver(useVPN=True, IpCheck=True)

    try:
        pageNum = 0
        while True:
            proxy_atmpt = 0
            while proxy_atmpt < 5:
                try:
                    if pageNum == 0:
                        driver.get(f'https://www.google.com/shopping/product/{found_gcode}/offers')
                    else:
                        driver.get(f'https://www.google.com{[a for a in soup.find_all("a",class_="internal-link") if a.text == "Next"][0].attrs["data-url"]}')
                    time.sleep(5)
                    driver.refresh()
                    time.sleep(10)
                    # Check for captcha page
                    while True:
                        if "https://www.google.com/sorry/index" in driver.current_url:
                            logger.debug(f"Captcha Detected, Waiting to be resolved manually")
                            driver.save_screenshot(f"/root/public/GcodeFinderBrandMpn(AF)/captcha2.png")
                            random_pause(10, 20)
                        else: break
                    pageHTML = driver.page_source
                    if "Our systems have detected unusual traffic from your computer network." in pageHTML:
                        proxy_atmpt += 1
                        logger.debug(f'Detected, trying again {proxy_atmpt}/5')
                    else:
                        soup = BeautifulSoup(pageHTML, 'html.parser')
                        break
                except Exception as e:
                    proxy_atmpt += 1
                    if proxy_atmpt == 5:
                        print(f"proxy_atmpt >> ", e)
                        raise e
            
            tempProdData = fetchProductData(soup, productID, productURL)
            if tempProdData["Scrapped Product URL"] == '':
                retry = True
            else:
                retry = False
            # Next page
            if len([a for a in soup.find_all("a",class_='internal-link') if a.text == "Next"]) > 0 and retry:
                pageNum += 1
            else:
                break
        # Updating mysql
        prodData = tempProdData
        if not retry:
            updateMYSQL({
                'GCODE': found_gcode,
                'DATA': prodData
            })
        else:
            print("Not found GCODE")
    except Exception as e:
        logger.debug(f"fetchMatchedData >> ", {found_gcode: e})
    finally:
        driver.quit()
        driver.service.stop()
        logger.debug(f"Scrapped ({found_gcode})")

def random_pause(min_time=2, max_time=5):
    """
    Add a random pause to simulate human thinking or waiting.
    """
    time.sleep(uniform(min_time, max_time))

# Check if our vendor site URL exits or not in listing of vendors on Google Shopping Product page
def fetchProductData(soup, productID, productURL):
    prodData = {
        'Product ID' : productID,
        'DB Product URL' : productURL,
        'Scrapped Product URL' : ''
    }
    for a in soup.find("tbody", id="sh-osd__online-sellers-cont").find_all("tr","sh-osd__offer-row"):
        if "Visit site" in a.find_all("a")[-1].text:
            siteURL = unquote(a.find_all("a")[-1].attrs['href']).replace('/url?q=', '')
            # If exists then fetch product URL from vendor list
            if 'https://www.afsupply.com/' in siteURL:
                prodData['Scrapped Product URL'] = siteURL
                logger.debug(f"Found our vendor.")
                return prodData
    return prodData


# Finding gcodes
def mainGoogleSearch(googleSearchPageLimit, searchKey):
    # print(searchKey)
    driver = init_selenium_driver(useVPN=True, IpCheck=True)
    if driver is None:
        logger.debug("Failed to initialize Selenium driver.")
        return []
    try:
        driver.maximize_window()
        driver.get(f"https://www.google.com/search?q={searchKey.replace(' ','+')}&oq={searchKey.replace(' ','+')}&tbm=shop&sclient=products-cc")
        # Extract page data
        if "https://consent.google.com/" in driver.current_url:
            ActionChains(driver).send_keys(Keys.TAB).perform()
            ActionChains(driver).send_keys(Keys.TAB).perform()
            ActionChains(driver).send_keys(Keys.TAB).perform()
            ActionChains(driver).send_keys(Keys.TAB).perform()
            ActionChains(driver).send_keys(Keys.ENTER).perform()
        
        # Opening all the search results
        for page in range(googleSearchPageLimit):
            try:
                time.sleep(20)
                driver.save_screenshot(f"/root/public/GcodeFinderBrandMpn(AF)/google-search-{page}.png")
                while True:
                    if "https://www.google.com/sorry/index" in driver.current_url:
                        logger.debug(f"Captcha Detected, Waiting to be resolved manually")
                        driver.save_screenshot(f"/root/public/GcodeFinderBrandMpn(AF)/captcha1{page}.png")
                        random_pause(10, 20)
                    else: break
                
                # Findning more results
                try:
                    moreResults = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="More results"]')
                    if moreResults.get_attribute('style') == 'transform: scale(0);': moreResults = None
                except: moreResults = None
                # Clicking more results
                if moreResults != None:
                    print(f'Page ({page + 1}).')
                    moreResults.send_keys(Keys.ENTER)
                    if "https://www.google.com/sorry/index" in driver.current_url:
                        raise Exception("Captcha Detected.")
                else:
                    # driver.get_screenshot_as_file("total_pages.png")
                    logger.debug(f"Total {page + 1} page(s) available.")
                    raise Exception("No `More results` found.")
            except Exception as e:
                print(f'googleSearchPageLimit >> {e}')
                break
        # Extracting gcode
        matchingBoxes = []
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # products from grid
        products_from_grid = soup.select('g-card.T98FId product-viewer-group > g-card ul li:first-child > div')
        if len(products_from_grid) == 0:
            products_from_grid = soup.select('div.MjjYud g-card.T98FId product-viewer-group ul > div > li:first-child > div')
            if len(products_from_grid) == 0:
                products_from_grid = soup.select('g-card.T98FId product-viewer-group > g-card > div > div > div > ul > div > li > div')
        
        print(f"Found {len(products_from_grid)} products")
        for grid in products_from_grid:
            if grid['data-cid'] != '':
                gcode = grid['data-cid']
                matchingBoxes.append(gcode)
        matchingBoxes = sorted(list(set(matchingBoxes)))
    except Exception as e:
        driver.get_screenshot_as_file(f"logs/Driver_error_({str(datetime.datetime.now()).replace(':', '-')}).png")
        logger.debug(f"mainGoogleSearch >> {e}")
    finally:
        driver.quit()
        driver.service.stop()
    return matchingBoxes

# Collecting gcodes
def googleProdSearchModules(searchKey, googleSearchPageLimit, productID, productURL):
    # print(productID)
    logger.debug(f"googleProdSearchModules for searchKey: {searchKey}, googleSearchPageLimit: {googleSearchPageLimit}")

    atmpt = 0
    matchingBoxes = []
    while len(matchingBoxes) == 0:
        if atmpt > 0: logger.debug(f"0 matching links found for {searchKey}. Possible IP issue, retrying.")
        matchingBoxes = mainGoogleSearch(googleSearchPageLimit, searchKey)
        logger.debug(f"Found {len(matchingBoxes)} Gcode(s).")
        atmpt += 1
        if atmpt == 2:
            logger.debug(f"{len(matchingBoxes)} matching links found for {searchKey} after attempting {atmpt} times.")
            break

    if len(matchingBoxes) > 0:
        print(matchingBoxes)
        try:
            start = time.perf_counter()
            for foundGcode in matchingBoxes:
                fetchMatchedData(foundGcode, productID, productURL)
                time.sleep(1)
            finish = time.perf_counter()
            logger.info(f'Finished scraping GCODEs in {round(finish - start, 2)} second(s)')
        except Exception as e:
            logger.debug(f"Scraping Gcode >> {e}")

# Core Function
def core(searchKey, productIDs, productURLs):
    googleSearchPageLimit = 10

    logger.debug(f"Processing ({searchKey})")
    try:
        productID = productIDs[searchKey]
        productURL = productURLs[searchKey]
        googleProdSearchModules(searchKey, googleSearchPageLimit, productID, productURL)
        logger.debug(f"Processed ({searchKey})")
    except Exception as e:
        logger.debug(f"Failed search for '{searchKey}': {e}")
