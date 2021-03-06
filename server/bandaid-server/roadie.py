"""Syncs all known band pages statuses 200/404 to redis sets"""
import requests 
import redis

# example url
# `curl https://www.bandsintown.com/a/1 | grep "upcomingEventsSection" | html2text -style pretty`
# `curl https://www.bandsintown.com/a/1 | grep "artistInfo" | html2text -style pretty`


def enumerator(url="https://www.bandsintown.com/a/1"):
    """
    What:
    ----
    Performs head request to confirm page exists and stores in queue

    Returns:
    ---
    Dictionary of True or false that page exists
    """
    r = requests.head(url)
    if r.status_code == 200:
        return url, 1
    else:
        return url, 0


def connectRedis():
    r = redis.Redis(host='localhost', port=6379,
                    charset="utf-8", decode_responses=True)
    try:
        r.ping()
    except redis.exceptions.ConnectionError:
        exit('Redis is not started.')
    return r


def updateRedis(rs, status, url):
    """
    What
    ---
    Updates redis sets active or inactive with url
    Returns:
    ---
    nothing
    """
    if status == 1:
        rs.sadd('active', url)
    else:
        rs.sadd('inactive', url)
    rs.hmset(url, {"name": url, "status_code": status})


def main():
    baseurl = "https://www.bandsintown.com/a/{}"
    rs = connectRedis()
    totaldonesofar = rs.scard('active') + rs.scard('inactive')
    i = totaldonesofar
    while i < 1674009:
        url, status = enumerator(baseurl.format(str(i)))
        updateRedis(rs, status, baseurl.format(str(i)))
        i += 1
        print(i)


if __name__ == "__main__":
    main()
