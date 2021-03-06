# -*- coding: utf-8 -*-
from crawler import simple_crawler_config
from crawler.simpleCrawler.SimpleCrawler import SimpleCrawler
from crawler.util.ProxyCheck import ProxyCheck


class Launcher(object):
    def __init__(self):
        if "redisbloom" == simple_crawler_config.BLOOM_FILTER_MODE.lower():
            import redis
            from crawler.util.RedisBloomFilter import RedisBloomFilter
            rconn = redis.Redis('127.0.0.1', 6379)
            self.bf = RedisBloomFilter(rconn, 'simple_crawler:bloom_filter')
        elif "pybloom" == simple_crawler_config.BLOOM_FILTER_MODE.lower():
            from crawler.util import BloomFilterUtil
            self.bf = BloomFilterUtil.FileBloomFilter(simple_crawler_config.BLOOM_FILTER_FILE)
        else:
            # 默认不使用过滤
            self.bf = None

    def start_crawler(self):
        parserList = simple_crawler_config.parserList
        crawler_list = []
        items = []
        for site in parserList:
            for url in site['urls']:
                print("start " + url)
                crawler_thread = SimpleCrawler(site, url, items)
                crawler_list.append(crawler_thread)
        for t in crawler_list:
            t.start()
        for t in crawler_list:
            t.join()
        # 如果启用了bloomFilter
        if self.bf:
            # bloomFilter过滤已抓取代理ip
            filter_item = self.bf.filter_proxy_ip_list(items)
            # 过滤不可用代理ip 因为需要联网验证，需要一定时间，开启合理数目的多线程可减少时间消耗
            filter_item = ProxyCheck.checkIpList(filter_item, 30)
            # 保存代理ip
            self.save_items(filter_item)
            # 保存成功的数据 在bloomfilter加标记
            self.bf.add_proxy_ip_all(filter_item)
        else:
            # 未启用bloomFilter
            filter_item = ProxyCheck.checkIpList(items, 30)
            self.save_items(filter_item)
        return filter_item

    def save_items(self, items):
        if 'sqlite' == simple_crawler_config.SAVE_MODE.lower():
            # sqlite 存储
            self.save_sqlite(items)
        elif 'mysql' == simple_crawler_config.SAVE_MODE.lower():
            # mysql存储
            self.save_mysql(items)
        else:
            self.save_json(items)

    def save_json(self, items):
        import json
        import codecs
        try:
            file = codecs.open(simple_crawler_config.JSON_FILE, 'a', encoding='utf-8')
            for item in items:
                line = json.dumps(dict(item), ensure_ascii=False) + "\n"
                file.write(line)
        except Exception, e:
            raise e
        finally:
            file.close()

    def save_sqlite(self, items):
        from crawler.sqliteClient.IPProxy import IPProxy
        try:
            dbClient = IPProxy(simple_crawler_config.SQLITE_FILE)
            dbClient.insertMany(items)
        except Exception, e:
            raise e
        finally:
            dbClient.disconnect()

    def save_mysql(self, items):
        import MySQLdb
        mysql_conf = simple_crawler_config.MYSQL_CONNECT
        mysql_conn = MySQLdb.connect(**mysql_conf)
        cur = mysql_conn.cursor()
        sql = (
            "insert into proxy_ip(ip,port,protocol,area,speed) values(%s,%s,%s,%s,%s)")
        try:
            args = []
            for item in items:
                item_list = (item['ip'], item['port'], item['protocol'], item['area'], item['speed'])
                args.append(item_list)
            cur.executemany(sql, args)
            mysql_conn.commit()
        except Exception, e:
            raise e
            mysql_conn.rollback()
        finally:
            cur.close()
            mysql_conn.close()
