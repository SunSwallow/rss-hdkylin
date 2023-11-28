import requests
import argparse
import json
from bs4 import BeautifulSoup
import PyRSS2Gen
import re
import datetime
from flask import Flask, render_template, request, send_from_directory, Response

def time_to_minutes(time_str):

    # Define a dictionary to hold the conversion values for each unit
    conversion = {'年': 525600,"月":1440*30, '天': 1440, '时': 60, '分': 1}

    # Use regular expressions to find all occurrences of time units and their values
    time_components = re.findall(r'(\d+)([年月天时分])', time_str)

    # Convert and sum up the minutes
    total_minutes = sum(int(value) * conversion[unit] for value, unit in time_components)

    return total_minutes
def parse_cookies(cookies_str):
    cookies = {}
    for cookie in cookies_str.split('; '):
        key, value = cookie.split('=', 1)
        cookies[key] = value
    return cookies

def get_torrent_info_hdkylin(table_row, passkey, args):
    free_flag = bool(table_row.find('img', class_='pro_free'))

    if args.only_free and not free_flag:
        return None
    
    if free_flag:
        free_time = table_row.find('span', title=True).text
    else:
        free_time = None

    hot_flag = bool(table_row.find('font', class_='hot'))

    if args.only_hot and not hot_flag:
        return None

    survival_time = table_row.select("td.rowfollow.nowrap span")[0].text
    # print("转换前：{}，转换后：{}".format(survival_time, time_to_minutes(survival_time)))

    if args.survival_time_limit > 0 and time_to_minutes(survival_time) > args.survival_time_limit:
        return None

    name = table_row.select("td.embedded  a b" )[0].text

    download_href = "https://www.hdkyl.in/" + table_row.select("td.embedded  a " )[1].get("href")
    download_href =  download_href + "&passkey={}".format(passkey)

    td_rowfollow = table_row.select("td.rowfollow")
    size = td_rowfollow[-5].text

    uploading_people = td_rowfollow[-4].text

    downloading_people = td_rowfollow[-3].text

    if args.downloading_people_limit > 0 and int(downloading_people) < args.downloading_people_limit:
        return None

    finished_people = td_rowfollow[-2].text

    

    description = "是否热门:{}\t是否免费:{}\t免费时间:{}\t存活时间:{}\t大小:{}\t上传人数:{}\t下载人数:{}\t完成人数:{}\n\n{}".format(
        hot_flag, free_flag, free_time, survival_time, size, uploading_people, downloading_people, finished_people, table_row.select("td.embedded" )[1].text)

    rss_item = PyRSS2Gen.RSSItem(title=name, link=download_href, description=description)

    return rss_item

def get_torrent_hdkylin(args, session, headers):
    cookies = parse_cookies(args.cookies)
    for name, value in cookies.items():
        session.cookies.set(name, value)

    proxies= {}

    response = session.get('https://www.hdkyl.in/torrents.php',
                           headers=headers,
                           proxies=proxies)
    soup = BeautifulSoup(response.text, 'html.parser')
    table_rows = soup.select('table.torrents > tr')[1:]

    items = []
    for table_row in table_rows:
        rss_item = get_torrent_info_hdkylin(table_row, args.passkey, args)
        if rss_item:
            items.append(rss_item)

    return items


user_headers = {
    'User-Agent': 'Edg/87.0.4280.88',
}

parser = argparse.ArgumentParser(description='Login to a website using cookies from command line.')
parser.add_argument('--cookies',type=str)
parser.add_argument("--passkey", type=str)
parser.add_argument("--only_free", type=int, default=1)
parser.add_argument("--only_hot", type=int, default=0)
parser.add_argument("--survival_time_limit", default=0, help="默认单位为分", type=int)
parser.add_argument("--port", default=80, type=int)
parser.add_argument("--downloading_people_limit", default=0, help="默认单位为人", type=int)
args = parser.parse_args()
print(args)
session = requests.Session()

app = Flask(__name__)

@app.route('/')
def rss():
    rss_items = get_torrent_hdkylin(args, session, user_headers)

    rss = PyRSS2Gen.RSS2(title='Coatsocold的HDKylin RSS订阅, Hotword启动', link="http://127.0.0.1:{}".format(args.port), description='自定义RSS订阅', pubDate=datetime.datetime.utcnow(), items=rss_items)
    rss = rss.to_xml()
    rss = rss.replace("iso-8859-1", "utf-8")
    r = Response(response=rss, status=200, mimetype="application/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r

app.run(host='0.0.0.0', port=args.port)
