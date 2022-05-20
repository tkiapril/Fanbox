from json import loads
from time import sleep
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup as bs
from requests import cookies, Session

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:93.0) ' \
     'Gecko/20100101 Firefox/93.0'
COOKIE = 'CHANGEME'

#REFERER_CREATOR = 'https://www.fanbox.cc/@{}'
#REFERER_POST = 'https://www.pixiv.net/fanbox/creator/{}/post/{}'


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class SessionExt(Session):
    def request(self, method, url, **kwargs):
        for i in range(10):
            try:
                r = super().request(method, url, **kwargs)
            except Exception:
                print(f"FAILED EXC {url}\n—{10-i} more retries left.")
                sleep(10)
                continue
            if r.status_code == 200:
                break
            else:
                print(f"FAILED {r.status_code} {url}\n—{10-i} more retries left.")
                sleep(10)
        else:
            raise Exception('Download failed after 10 attempts.')

        sp = urlsplit(url)
        pathstr = sp.scheme.replace('/', '_') \
            + '/' + sp.netloc.replace('/', '_') \
            + '/' + (sp.path.strip('/') if sp.path else '_')
        pathstr = pathstr + '?' + sp.query.replace('/', '_') \
            if sp.query else pathstr
        pathstr = pathstr + '#' + sp.fragment.replace('/', '_') \
            if sp.fragment else pathstr
        p = Path(pathstr)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('wb') as wb:
            wb.write(r.content)
        print(
            f'{sizeof_fmt(len(r.content))} {r.status_code} {url}'
        )
        return r


def main():
    s = SessionExt()
    s.headers.update({
        'User-Agent': UA,
        'DNT': '1',
        'Origin': 'https://www.fanbox.cc',
        'Accept': 'application/json, text/plain, */*'
    })
    s.cookies.set_cookie(
        cookies.create_cookie(
            domain='.fanbox.cc',
            name='FANBOXSESSID',
            value=COOKIE
        )
    )

    r = s.get('https://api.fanbox.cc/plan.listSupporting')
    for creatorId in [
        #i['user']['userId'] for i in loads(r.text)['body']
        i['creatorId'] for i in loads(r.text)['body']
    ]:
        nextUrl = None
        r = s.get(
            f'https://api.fanbox.cc/creator.get?creatorId={creatorId}',
            headers={
                'Referer': 'https://www.fanbox.cc/'
            }
        )
        fanbox_body = loads(r.text)['body']
        if fanbox_body['user']['iconUrl']:
            s.get(
                fanbox_body['user']['iconUrl'],
                headers={
                    'Referer': 'https://www.fanbox.cc/'
                }
            )
        if fanbox_body['coverImageUrl']:
            s.get(
                fanbox_body['coverImageUrl'],
                headers={
                    'Referer': 'https://www.fanbox.cc/'
                }
            )
        for item in fanbox_body['profileItems']:
            if 'imageUrl' in item:
                s.get(
                    item['imageUrl'],
                    headers={
                        'Referer': 'https://www.fanbox.cc/'
                    }
                )
            if 'thumbnailUrl' in item:
                s.get(
                    item['thumbnailUrl'],
                    headers={
                        'Referer': 'https://www.fanbox.cc/'
                    }
                )
        while True:
            url = nextUrl or \
                'https://api.fanbox.cc/' \
                f'post.listCreator?creatorId={creatorId}&limit=10'
            url = "https://api.fanbox.cc" + url \
                if not url.startswith('https://') else url
            r = s.get(
                url,
                headers={
                    'Referer': 'https://www.fanbox.cc/'
                }
            )
            fanbox_body = loads(r.text)['body']
            posts = fanbox_body['post'] \
                if 'post' in fanbox_body else fanbox_body
            for post_item in [i for i in posts['items'] if i['body']]:
                id = int(post_item['id'])
                rqinfo = s.get(
                    f'https://api.fanbox.cc/post.info?postId={id}',
                    headers={
                        'Referer': 'https://www.fanbox.cc/'
                    }
                )
                info_body = loads(rqinfo.text)['body']
                post_body = info_body['body']
                download_list = []
                if post_body:
	                if post_item['coverImageUrl']:
	                    download_list.append(post_item['coverImageUrl'])
	                if info_body['imageForShare']:
	                    download_list.append(info_body['imageForShare'])
	                if 'imageMap' in post_body and post_body['imageMap']:
	                    download_list.extend(
	                        [i['originalUrl']
	                         for i in post_body['imageMap'].values()
	                         ]
	                    )
	                    download_list.extend(
	                        [i['thumbnailUrl']
	                         for i in post_body['imageMap'].values()
	                         ]
	                    )
	                if 'fileMap' in post_body and post_body['fileMap']:
	                    download_list.extend(
	                        [i['url'] for i in post_body['fileMap'].values()]
	                    )
	                if 'images' in post_body and post_body['images']:
	                    download_list.extend(
	                        [i['originalUrl'] for i in post_body['images']]
	                    )
	                    download_list.extend(
	                        [i['thumbnailUrl'] for i in post_body['images']]
	                    )
	                if 'files' in post_body and post_body['files']:
	                    download_list.extend(
	                        [i['url'] for i in post_body['files']]
	                    )
	                if 'html' in post_body and post_body['html']:
	                    soup = bs(post_body['html'])
	                    for img in soup.find_all('img'):
	                        download_list.append(
	                            img['data-src-original']
	                            if img.has_attr('data-src-original')
	                            else img['src']
	                        )
	                    for a in soup.find_all(href=True):
	                        sp = urlsplit(a['href'])
	                        #if sp.netloc == "fanbox.pixiv.net" \
	                        if sp.netloc == "downloads.fanbox.cc" \
	                           and sp.path.strip('/').startswith('files') \
	                           or sp.path.strip('/').startswith('images'):
	                            # just in case
	                            download_list.append(a['href'])
	                for dl in download_list:
	                    s.get(
	                        dl,
	                        headers={
	                            'Referer': 'https://www.fanbox.cc/'
	                        }
	                    )
                sleep(2)

            nextUrl = posts['nextUrl'] if 'nextUrl' in posts else None
            if not nextUrl:
                break


if __name__ == '__main__':
    main()
