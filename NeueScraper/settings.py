# -*- coding: utf-8 -*-

# Scrapy settings for NeueScraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = 'NeueScraper'

SPIDER_MODULES = ['NeueScraper.spiders']
NEWSPIDER_MODULE = 'NeueScraper.spiders'

LOG_ENABLED = True

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'NeueScraper (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
#DOWNLOAD_DELAY = 3
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False
COOKIES_DEBUG = True

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
   'Accept-Language': 'en',
   'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    'NeueScraper.middlewares.NeuescraperSpiderMiddleware': 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.redirect.RedirectMiddleware": 600,
    "NeueScraper.middlewares.ProxyAwareRedirectMiddleware": 601
}

# Für FilesPipeline-Downloads (PDF) Redirects zulassen
MEDIA_ALLOW_REDIRECTS = True
REDIRECT_MAX_TIMES = 20

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {'NeueScraper.pipelines.MyFilesPipeline': 1, 'NeueScraper.pipelines.MyWriterPipeline': 100}
FILES_STORE = 'sftp://entscheidsuche.ch'
SFTP_HOST ='entscheidsuche.ch'
#FILES_STORE = 's3://entscheidsuche.ch/scraper/'
#FILES_STORE_S3_ACL = 'public-read'
#AWS_ENDPOINT_URL = 'https://s3.eu-west-3.amazonaws.com'
#AWS_ACCESS_KEY_ID
#AWS_SECRET_ACCESS_KEY
#AWS_REGION_NAME='eu-west-3'
#AWS_DEFAULT_REGION='eu-west-3'
#AWS_PROFILE='default'
#AWS_USE_SSL = True
#AWS_VERIFY = True
#FTP_USER = 'Scraper@entscheidsuche.ch'
#FTP_PASSWORD
FILES_URLS_FIELD = "PDFUrls"
FILES_RESULT_FIELD = "PDFFiles"
#FEED_URI ='s3://entscheidsuche.ch/scraper/dump.csv'
#ITEM_	S = {
#    'NeueScraper.pipelines.NeuescraperPipeline': 300,
#}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'


