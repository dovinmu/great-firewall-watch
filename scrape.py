from spaces_interface import load_termlist, write_error, write_search_results, write_logs
from storage import save_search_results
from user_agent import get_user_agent

from bs4 import BeautifulSoup
from datetime import datetime
import json
import pandas as pd
import random
import re
import requests
import time

MAX_PICTURES_PER = 5

def query_baidu(term):
    baidu_template = 'https://image.baidu.com/search/index?tn=baiduimage&word={}'
    user_agent = get_user_agent()
    url = 'https://image.baidu.com/search/flip?tn=baiduimage&ie=utf-8&word='+term+'&ct=201326592&v=flip'
    r = requests.get(url, timeout=10,
                proxies={'https':None, 'http':None},
                headers={'User-Agent':user_agent})
    urls = re.findall('"objURL":"(.*?)",',r.text,re.S)
    return urls

def query_google(term):
    google_template = 'https://www.google.com/search?q={}&tbm=isch'
    r = requests.get(google_template.format(term))
    soup = BeautifulSoup(r.text, features="html.parser")
    urls = [tag.get('src') for tag in soup.find_all('img') if tag.get('src')[:4] == 'http']
    return urls

def printable_time(days=0, hours=0, minutes=0, seconds=0):
    total_seconds = 24*60*60*days + 60*60*hours + 60*minutes + seconds
    if total_seconds < 60:
        return f"{round(total_seconds)} seconds"
    if total_seconds < 60*60:
        return f"{round(total_seconds/60, 1)} minutes"
    if total_seconds < 2*24*60*60:
        return f"{round(total_seconds/(60*60), 1)} hours"
    total_days = int(total_seconds/(24*60*60))
    remainder = total_seconds % (24*60*60)
    return f"{total_days} days, {printable_time(seconds=remainder)}"

def run(total_hours=24, hourly_limit=200, shuffle=False):


    google_fails = []
    baidu_fails = []

    google_results = []
    baidu_results = []

    total_requests = int(total_hours * hourly_limit)
    total_time = 60*60*total_hours
    wait_time = total_time / total_requests
    daily_max_requests = hourly_limit * 24

    termlist = load_termlist()

    try:
        import os
        os.mkdir('search_results')
    except Exception as e:
        print("could not make directory", e)
        # pass

    # not sure if shuffle is needed, if so try shuffling index
    if shuffle:
        raise NotImplementedError()
    #     print("shuffling termlist")
    #     random.shuffle(termlist)
    if len(termlist) > daily_max_requests:
        print("Warning: termlist length is", len(termlist), "while max daily requests will be", daily_max_requests)
    if len(termlist) > total_requests:
        print(f"Warning: only querying {total_requests} of {len(termlist)} total terms (not enough time specified)")
    print("querying", total_requests, "terms for", printable_time(seconds=total_time))

    term_idx = 0
    google_img_count = 0
    baidu_img_count = 0

    start_ts = time.time()
    for i in range(0, total_requests):
        start_iter_ts = time.time()
        try:
            english_term = termlist.loc[term_idx].english
            chinese_term = termlist.loc[term_idx].chinese
        except:
            print("out of terms")
            break
        print(f'request {i}, term idx {term_idx}: "{english_term}", "{chinese_term}"')
        if not english_term:
            print("\tskipping Google for term (English term not present)")
        else:
            try:
                urls = query_google(english_term)
                print(f"\tGoogle got {len(urls)} images")
                result = {}
                result['english_term'] = english_term
                result['chinese_term'] = chinese_term
                result['urls'] = urls[:MAX_PICTURES_PER]
                result['ts'] = time.time()
                google_results.append(result)
            except Exception as e:
                google_fails.append(e)
                print("\tGoogle fail")
        if not chinese_term:
            print("\tskipping Baidu for term (Chinese term not present)")
        else:
            try:
                urls = query_baidu(chinese_term)
                print(f"\tbaidu got {len(urls)} images")
                result = {}
                result['english_term'] = english_term
                result['chinese_term'] = chinese_term
                result['urls'] = urls[:MAX_PICTURES_PER]
                result['ts'] = time.time()
                baidu_results.append(result)
            except Exception as e:
                baidu_fails.append(e)
                print("\tBaidu fail")

        term_idx += 1

        # account for the time the calls took
        took = time.time() - start_iter_ts
        # add in random jitter
        time_noise = random.random()*2 - 1
        # print("adding noise to wait time", printable_time(seconds=time_noise))

        # cache results. this is a backup and not meant to be a reliable data store
        google_img_count += write_search_results(google_results, 'google')
        baidu_img_count += write_search_results(baidu_results, 'baidu')
        time.sleep(max(0, wait_time - took + time_noise))
    write_logs(f'wrote {google_img_count} google images and {baidu_img_count} baidu images')
    write_error(f"Baidu failures: {len(baidu_fails)}")
    write_error(f"Google failures: {len(google_fails)}")
    print("took", printable_time(seconds=time.time() - start_ts))

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        write_error(str(e))
        write_logs("got an error while running scraper")