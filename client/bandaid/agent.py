"""Gets latest band data for a particular band and adds to user watchlist."""
from bs4 import BeautifulSoup as bs
import datetime
from datetime import date
from os import environ, getcwd, path
import requests
import argparse
from pathlib import Path
import re
import sqlite3
import sys
import shutil


__version__ = "1.1.2"


def printlogo():
    """
    Prints logo
    Returns nothing
    """
    print("")
    print("     ;;;;;;;;;;;;;;;;;;; ")
    print("     ;;;;;;;;;;;;;;;;;;; ")
    print("     ;                 ; ")
    print("     ;     bandaid     ; ")
    print("     ;                 ; ")
    print("     ;  +-----------+  ; ")
    print("     ;  |by JC 2020 |  ; ")
    print("     ;  +-----------+  ; ")
    print("     ;                 ; ")
    print(",;;;;;            ,;;;;; ")
    print(";;;;;;            ;;;;;; ")
    print("`;;;;'            `;;;;' ")
    print("")


def initDB(dbpath, zipcode, username, lat, lng):
    open(dbpath, "w+")
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute('''CREATE TABLE tracker
             (id integer PRIMARY KEY, date_added text, date_last_checked text,
             band text, on_tour integer, coming_to_town integer,
             notified integer, push_updates integer, zipcode integer,
             lat FLOAT, long FLOAT)''')
    c.execute('''CREATE TABLE user
             (id integer PRIMARY KEY, date_added text, username text,
             zipcode integer, os text, lat FLOAT, long FLOAT )''')
    c.execute('''CREATE TABLE events
              (id integer PRIMARY KEY, date_added text, band text,
              date_of_event text, city_of_event text, venue_name text,
              city_lat FLOAT, city_long FLOAT)''')
    currentdate = datetime.datetime.now()
    opersystem = sys.platform
    c.execute('insert into user(date_added, username, zipcode, os, lat, long)\
              values(?, ?, ?, ?, ?, ?)',
              (currentdate, username, zipcode, opersystem, lat, lng))
    conn.commit()
    conn.close()


def checkFirstRun():
    """
    Check if file exists for the sqlite database and
    if not creates it and cfg and gets zipcode
    """
    my_cfg = Path.home() / ".bandaid" / "bandaid.cfg"
    my_db = Path.home() / ".bandaid" / "bandaid.db"
    if Path(f'{Path.home()}/.bandaid/').exists():
        return my_db
    print("First run, making the donuts...")
    Path.mkdir(Path.home() / ".bandaid", exist_ok=True)
    zipcode = inputZip()
    lat, lng = getLatLng(zipcode)
    with open(my_cfg, "w+") as f:
        f.write('DBPATH=~/.bandaid/bandaid.db\n')
        f.write(f'ZIPCODE={zipcode}')
    user = (lambda: environ["USERNAME"]
            if "C:" in getcwd() else environ["USER"])()
    initDB(my_db, zipcode, user, lat, lng)
    print(f"Database and config file created at {my_cfg}")
    return my_db


def inputZip() -> int:
    """
    Returns integer zipcode only
    """
    while True:
        try:
            return int(input("Enter your zipcode for concerts near you: "))
        except ValueError:
            print("Input only accepts numbers.")


def getZipCode(dbpath) -> (int, float, float):
    """
    Gets zipcode from user table in sqlite db (check bandaid.cfg for path)

    Returns
    ---
    zipcode int
    lat float
    long float
    """
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute("select zipcode, lat, long from user where id=1")
    conn.commit()
    zipcode = c.fetchone()
    conn.close()
    return zipcode[0], zipcode[1], zipcode[2]


def getLatLng(zipcode=22207) -> (float, float):
    """
    Uses free service to get latitude and longitude and store
    Returns
    ---
    lat float var for user table
    lng float var for user table

    """
    r = requests.get(f"https://geocode.xyz/{zipcode}?json=1")
    data = r.json()
    lat = data.get('latt')
    lng = data.get('longt')
    return lat, lng


def watchlist(bandname, dbpath):
    """
    Add band to watchlist, initialize watchlist service and db is doesn't exist
    """
    print("In future versions, there will be an\
          option to auto check every hour.")
    print("For now, you have to run the bandaid -f or bandaid --fetch command to\
          get current status of all bands tracking")
    promptsure = "y"
    promptsure = input(f"Are you sure you want to watch {bandname}? (y/n): ")
    if promptsure in ['n', 'no', 'N', 'No', 'NO']:
        exit('Thanks!')
    if promptsure not in ['y', 'Y', 'n', 'N']:
        print('Assuming you meant yes, and moving forward with tracking.')
    zipcode, lat, lng = getZipCode(dbpath)
    promptzip = input(f"Do you want to track {bandname} to {zipcode}? (y/n): ")
    if promptzip in ["n", "N"]:
        zipcode = input(f"What zip would you like for {bandname}? ")
    sqlstatement = "insert into tracker(date_added, date_last_checked,\
                    band, on_tour, zipcode, lat, long) values(?,?,?,?,?,?,?)"
    insertSQL(sqlstatement, dbpath, (datetime.datetime.now(),
                                     datetime.datetime.now(),
                                     bandname, 1, int(zipcode), lat, lng))
    print('Added band to tracker database. To get status at any time,\
          rerun with -f and -b band')
    # TODO ask user if they want to be automatically notified or manually check
    # conn = sqlite3.connect(Path.home() / ".bandaid.db")
    # TODO add supervisord creation and launchctl and permissions potentially


def getBand(bandname, dbpath):
    """
    Get band page and related data
    """
    indb = executeSingleSQL("Select band from tracker where band = ?",
                            dbpath, (bandname,))
    if indb is not None:
        print(
            f"You are already tracking {bandname}. Run `bandaid - f {bandname}` to get detailed info.")
    baseurl = "https://www.bandsintown.com/{}"
    r = requests.get(baseurl.format(bandname))
    if r.status_code == 200:
        if "No upcoming events</div>" in r.text:
            print(f"No upcoming events for {bandname}.")
        else:
            print(f"{bandname} is on tour!")
            bdata = bs(r.text, 'html.parser')
            soup = bdata.find("div", class_=re.compile('upcomingEvents*'))
            eventas = soup.find_all("a", class_=re.compile('event*'))
            print(f"{bandname} dates and locations:")
            for item in eventas:
                divs = item.find_all("div", class_=re.compile('event*'))
                date_of_concert = divs[1].get_text()
                date_of_concert += str(date.today().year)
                city_state = str(divs[5].get_text())
                city_state = city_state + ", USA"
                city_state = city_state.strip()
                city_state_updated = ''.join(city_state.split())
                event_venue = str(divs[6].get_text())
                lat, lng = getLatLng(city_state_updated)
                sql = "insert into events(date_added,\
                                          band, date_of_event,\
                                          city_of_event, venue_name,\
                                          city_lat, city_long)\
                                          values(?, ?, ?, ?, ?, ?, ?)"
                insertSQL(sql, dbpath, (datetime.datetime.now(), bandname,
                                        date_of_concert, city_state,
                                        event_venue, lat, lng)
                          )
                print(f"{date_of_concert} - {city_state} - {event_venue}")
                # TODO add in calculate distance from zipcode
            if indb == None:
                bandtrack = input(
                    f"Would you like to track {bandname}? (y/n) ")
                if bandtrack in ['y', 'Y']:
                    print(f"Adding {bandname} to your watchlist now...")
                    watchlist(bandname, dbpath)
                else:
                    print("To track if they are coming near you, add to\
                        watchlist next time you run.")
                    exit()
    else:
        exit('Nothing exists for that band, try another, how about Radiohead?')


def prepper() -> list:
    """
    Process all runtime arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--band', dest='bandname',
                        help="band to lookup", type=str, nargs='+')
    parser.add_argument('-w', '--watchlist', dest='watchlist',
                        action='store_true', help="add to watchlist")
    parser.add_argument('-f', '--fetch', dest='fetcher',
                        action='store_true', help="fetch a band (with -b flag)\
                        or no extra flag for all bands tracking current status"
                        )
    parser.add_argument('-c', '--config', dest='config', action='store_true',
                        help='print out current config info')
    parser.add_argument('-v', '--version', action='version',
                        version="%(prog)s ("+__version__+")")
    parser.add_argument('-r', '--reset', dest='reset', action='store_true',
                        help='resets everything back to original download')
    args = parser.parse_args()
    return args


def executeArraySQL(sqlstatement, dbpath):
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute(sqlstatement)
    return c.fetchall()


def executeSingleSQL(sqlstatement, dbpath, tuplevar):
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute(sqlstatement, tuplevar)
    return c.fetchone()


def insertSQL(sqlstatement, dbpath, tuplevar) -> None:
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute(sqlstatement, tuplevar)
    conn.commit()
    conn.close()


def fetchCurrentStatus(bandname, dbpath):
    """
    Get current status and update in db for band or all bands
    Note: If bandname is blank, it is just foo, so grabs all bands
    """
    # check if bandname not passed and then load all tracked bands
    if bandname == 'foo':
        sqlcall = "select band from tracker"
        listofbands = executeArraySQL(sqlcall, dbpath)
        for band in listofbands:
            print(band)
        exit('thanks for trying out multiple bands, not fully working yet')
    bandinfo = executeSingleSQL("select date_added from tracker where band=?",
                                (bandname,))
    print(bandinfo)
    exit("not fully implemented yet")


def printConfig(dbpath) -> None:
    """
    From argparse - c - -config to print the bandaid.cfg file
    """
    conn = sqlite3.connect(str(dbpath))
    c = conn.cursor()
    c.execute('''select * from user where id = 1''')
    conn.commit()
    data = c.fetchone()
    print(f"Date Registered: {data[1]}")
    print(f"Username: {data[2]}")
    print(f"Zip Code: {data[3]}")
    print(f"Lat/Lng: {data[5]}/{data[6]}")
    conn.close()
    exit("Thanks for checking the configuration.")


def main():
    """
    Main function that runs everything
    """
    args = prepper()
    if args.reset:
        shutil.rmtree(Path.home() / ".bandaid")
        exit('Directory wiped and data wiped.')
    dbpath = checkFirstRun()
    if args.config:
        printConfig(dbpath)
    printlogo()
    if args.fetcher and args.bandname:
        fetchCurrentStatus(args.bandname, dbpath)
    if args.fetcher and not args.bandname:
        fetchCurrentStatus('foo', dbpath)
    if args.bandname:
        getBand(" ".join(args.bandname), dbpath)
    else:
        exit('Must set band name -h for help.')


if __name__ == "__main__":
    main()
